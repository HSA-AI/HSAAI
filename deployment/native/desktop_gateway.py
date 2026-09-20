#!/usr/bin/env python3
"""
HSAAI Desktop Session Gateway API (Phase 6 integration).

Manages REAL remote Linux desktop sessions (Xvfb -> openbox -> x11vnc -> noVNC)
behind a secure, session-isolated REST API.

Endpoints:
  POST   /desktop/session                     create + start a session
  GET    /desktop/session/{id}                session status
  GET    /desktop/sessions                    list sessions
  POST   /desktop/session/{id}/start          start (idempotent)
  POST   /desktop/session/{id}/stop           stop
  POST   /desktop/session/{id}/restart        restart
  DELETE /desktop/session/{id}                stop + remove record
  GET    /desktop/session/{id}/snapshot.png   FFmpeg x11grab frame

Security:
  - X-API-Token header required (DESKTOP_API_TOKEN env; random if unset)
  - Sessions bind VNC to 127.0.0.1 only; browser reaches via noVNC websocket
  - Per-session display/port isolation
"""
import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# v3 portable: runtime dir & desktop script resolved from env (set by hsaai-ctl/hsaai-env.sh)
# with fallbacks relative to this file: <project>/../runtime and <project>/deployment/native/
_SELF = Path(__file__).resolve()
_PROJECT = _SELF.parent.parent          # <project>/deployment/native -> <project>
RUNTIME = Path(os.getenv("HSAAI_RUNTIME") or _PROJECT.parent / "runtime")
SESSIONS_DB = RUNTIME / "desktop" / "sessions.json"
DESKTOP_SCRIPT = Path(os.getenv("HSAAI_DESKTOP_SCRIPT") or _SELF.parent / "desktop-session.sh")
FFMPEG = os.getenv("FFMPEG", "ffmpeg")

API_TOKEN = os.getenv("DESKTOP_API_TOKEN") or secrets.token_hex(16)
BASE_VNC_PORT = int(os.getenv("DESKTOP_BASE_VNC_PORT", "5999"))
BASE_NOVNC_PORT = int(os.getenv("DESKTOP_BASE_NOVNC_PORT", "6080"))
BASE_DISPLAY = int(os.getenv("DESKTOP_BASE_DISPLAY", "90"))
MAX_SESSIONS = int(os.getenv("DESKTOP_MAX_SESSIONS", "5"))
SESSION_TTL_IDLE = int(os.getenv("DESKTOP_SESSION_TTL_IDLE", "3600"))

app = FastAPI(title="HSAAI Desktop Session Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["self"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Token"],
)


def _load_sessions() -> dict:
    if SESSIONS_DB.exists():
        try:
            return json.loads(SESSIONS_DB.read_text())
        except Exception:
            return {}
    return {}


def _save_sessions(data: dict) -> None:
    SESSIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_DB.write_text(json.dumps(data, indent=2))


def _auth(token: str | None) -> None:
    if not token or not secrets.compare_digest(token, API_TOKEN):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Token")


def _session_running(sid: str) -> bool:
    sess_dir = RUNTIME / "desktop" / sid / "pids"
    if not sess_dir.exists():
        return False
    for pid_file in sess_dir.glob("*.pid"):
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            continue
    return False


class CreateRequest(BaseModel):
    geometry: str = Field(default="1440x900x24", pattern=r"^\d+x\d+x24$")


def _allocate_slot() -> int:
    sessions = _load_sessions()
    used = {s.get("slot") for s in sessions.values() if s.get("status") != "stopped"}
    for slot in range(MAX_SESSIONS):
        if slot not in used:
            return slot
    raise HTTPException(status_code=409, detail="no free desktop slots")


@app.post("/desktop/session")
def create_session(req: CreateRequest, x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    slot = _allocate_slot()
    sid = f"ds-{slot}-{secrets.token_hex(3)}"
    env = dict(
        os.environ,
        HSAAI_DESKTOP_DISPLAY=str(BASE_DISPLAY + slot),
        HSAAI_VNC_PORT=str(BASE_VNC_PORT - slot),  # 5999, 5998, ...
        HSAAI_NOVNC_PORT=str(BASE_NOVNC_PORT + slot * 10),
        HSAAI_DESKTOP_GEOM=req.geometry,
    )
    r = subprocess.run(["bash", str(DESKTOP_SCRIPT), sid, "start"],
                       capture_output=True, text=True, env=env, timeout=60)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=f"session start failed: {r.stderr[-300:]}")
    sessions = _load_sessions()
    sessions[sid] = {
        "id": sid, "slot": slot, "status": "running",
        "display": BASE_DISPLAY + slot,
        "vnc_port": BASE_VNC_PORT - slot,
        "novnc_port": BASE_NOVNC_PORT + slot * 10,
        "geometry": req.geometry,
        "created_at": int(time.time()), "last_used": int(time.time()),
    }
    _save_sessions(sessions)
    s = sessions[sid]
    return {"id": sid, "status": "running", "display": s["display"],
            "novnc_url": f"/vnc.html?host={{window_host}}&port={s['novnc_port']}",
            "vnc_port_local": s["vnc_port"]}


def _get_session(sid: str, require_running: bool = False) -> dict:
    if not re.fullmatch(r"ds-\d-[0-9a-f]+", sid):
        raise HTTPException(status_code=400, detail="malformed session id")
    sessions = _load_sessions()
    if sid not in sessions:
        raise HTTPException(status_code=404, detail="session not found")
    s = sessions[sid]
    if require_running and not _session_running(sid):
        s["status"] = "stopped"
        _save_sessions(sessions)
        raise HTTPException(status_code=409, detail="session not running")
    return s


@app.get("/desktop/sessions")
def list_sessions(x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    sessions = _load_sessions()
    out = []
    for sid, s in sessions.items():
        s = dict(s)
        s["status"] = "running" if _session_running(sid) else "stopped"
        out.append(s)
    return {"sessions": out, "max_slots": MAX_SESSIONS}


@app.get("/desktop/session/{sid}")
def get_session(sid: str, x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    s = _get_session(sid)
    s = dict(s)
    s["status"] = "running" if _session_running(sid) else "stopped"
    return s


def _act(sid: str, action: str) -> dict:
    s = _get_session(sid)
    env = dict(
        os.environ,
        HSAAI_DESKTOP_DISPLAY=str(s["display"]),
        HSAAI_VNC_PORT=str(s["vnc_port"]),
        HSAAI_NOVNC_PORT=str(s["novnc_port"]),
        HSAAI_DESKTOP_GEOM=s.get("geometry", "1440x900x24"),
    )
    r = subprocess.run(["bash", str(DESKTOP_SCRIPT), sid, action],
                       capture_output=True, text=True, env=env, timeout=90)
    sessions = _load_sessions()
    sessions[sid]["status"] = "stopped" if action == "stop" else (
        "running" if _session_running(sid) else "stopped")
    sessions[sid]["last_used"] = int(time.time())
    _save_sessions(sessions)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=f"{action} failed: {r.stderr[-300:]}")
    return {"id": sid, "status": sessions[sid]["status"], "action": action}


@app.post("/desktop/session/{sid}/start")
def start_session(sid: str, x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    return _act(sid, "start")


@app.post("/desktop/session/{sid}/stop")
def stop_session(sid: str, x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    return _act(sid, "stop")


@app.post("/desktop/session/{sid}/restart")
def restart_session(sid: str, x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    return _act(sid, "restart")


@app.delete("/desktop/session/{sid}")
def delete_session(sid: str, x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    _get_session(sid)
    _act(sid, "stop")
    sessions = _load_sessions()
    sessions.pop(sid, None)
    _save_sessions(sessions)
    return {"id": sid, "deleted": True}


@app.get("/desktop/session/{sid}/snapshot.png")
def snapshot(sid: str, x_api_token: str | None = Header(default=None)):
    _auth(x_api_token)
    s = _get_session(sid, require_running=True)
    out = RUNTIME / "desktop" / sid / "snapshot.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h, _ = s.get("geometry", "1440x900x24").split("x")
    r = subprocess.run(
        [FFMPEG, "-y", "-f", "x11grab", "-video_size", f"{w}x{h}",
         "-i", f":{s['display']}", "-frames:v", "1", str(out)],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not out.exists():
        raise HTTPException(status_code=500, detail="snapshot failed")
    return Response(content=out.read_bytes(), media_type="image/png")


@app.get("/health")
def health():
    return {"status": "ok", "service": "hsaai-desktop-gateway"}


if __name__ == "__main__":
    # keep the token file in sync with the RUNNING gateway (ctl pins it via env);
    # masked print so secrets never land in log files
    _tokfile = RUNTIME / "desktop-gateway-token.txt"
    _tokfile.write_text(API_TOKEN)
    try:
        os.chmod(_tokfile, 0o600)
    except OSError:
        pass
    print(f"[desktop-gateway] API token: {API_TOKEN[:4]}…{API_TOKEN[-2:]} (full value in {_tokfile})")
    # SECURITY FIX (audit P2-4): default to loopback — this control plane spawns
    # X/VNC sessions and previously listened on all interfaces by default.
    uvicorn.run(app, host=os.getenv("DESKTOP_API_HOST", "127.0.0.1"), port=int(os.getenv("DESKTOP_API_PORT", "8600")))
