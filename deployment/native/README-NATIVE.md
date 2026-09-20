# HSAAI Native Deployment (Dockerless) — Verified Reference Architecture

Use this path when the host **cannot** run Docker Engine (no CAP_SYS_ADMIN,
read-only cgroups, no systemd — e.g. hardened containers, Firecracker/Kata
sandboxes, restricted CI runners). Everything runs as a normal unprivileged
user with process isolation, health checks and a service manager.

```
Browser ──► Next.js 15 standalone (:3000)
                │  HTTP/WS
                ▼
        backend_core FastAPI (:8000)
                ├── PostgreSQL 17 (:5432)   alembic migrations, 59 tables
                ├── Redis 8 (:6379)         cache / budgets / safety state
                ├── Qdrant 1.19 (:6333)     hsaai_knowledge collection
                └── Desktop Gateway (:8600) manages REAL desktop sessions
                          ├── Xvfb :99 (existing binary)
                          ├── openbox (WM) + xterm/xclock/xcalc (real X11 apps)
                          ├── x11vnc :5999 (localhost-only, password-protected)
                          ├── noVNC :6080 (browser client via websockify)
                          └── FFmpeg (x11grab snapshots / streaming)
```

## Directory layout (this repository)

```
deployment/native/
├── hsaai-ctl            # start/stop/restart/status for the whole stack
├── hsaai-env.sh         # shared env (paths, ports)
├── desktop-session.sh   # per-session desktop lifecycle (start/stop/restart)
├── desktop_gateway.py   # REST API: POST/GET/DELETE /desktop/session[...]
├── setup-runtime.sh     # user-space provisioning of PG/Redis/x11 stack
├── audit-hsaai.py       # static audit (syntax, compose, env alignment)
└── test-desktop-input.py# end-to-end input verification over real VNC
```

## Quick start (Linux, unprivileged user)

```bash
# 0) prerequisites: python3.12+ venv, node 20+, internet for first install
source deployment/native/hsaai-env.sh

# 1) data services (example: Debian user-space provisioning — no root needed)
bash deployment/native/setup-runtime.sh           # extracts official .debs
pg_ctl -D $HSAOI_DATA/pgdata start                # or: hsaai-ctl start postgres
redis-server --daemonize yes                      # or: hsaai-ctl start redis
./qdrant                                          # or: hsaai-ctl start qdrant

# 2) backend
python3 -m venv .venv-backend
.venv-backend/bin/pip install -r services/backend_core/requirements.txt
export DATABASE_URL="postgresql+psycopg://hsaai:<pw>@127.0.0.1:5432/hsaai"
export REDIS_URL="redis://127.0.0.1:6379/0" QDRANT_URL="http://127.0.0.1:6333"
hsaai-ctl start backend        # runs alembic upgrade head automatically
curl localhost:8000/ready      # → {"status":"ready", ...}

# 3) frontend
cd apps/web && npm install && npm run build && cd ../..
hsaai-ctl start web            # node .next/standalone/server.js on :3000

# 4) remote desktop (real X11, no fake HTML mock)
hsaai-ctl start desktop        # Xvfb+openbox+xterm+x11vnc+noVNC
hsaai-ctl start gateway        # REST API on :8600 (session lifecycle)
open http://localhost:6080/vnc.html
```

## Desktop Session API (Phase 6)

```bash
TOKEN=$(cat runtime/desktop-gateway-token.txt)

curl -X POST localhost:8600/desktop/session \
     -H "X-API-Token: $TOKEN" -H "Content-Type: application/json" \
     -d '{"geometry":"1280x800x24"}'

curl localhost:8600/desktop/session/<id>          -H "X-API-Token: $TOKEN"
curl -X POST  localhost:8600/desktop/session/<id>/restart -H "X-API-Token: $TOKEN"
curl localhost:8600/desktop/session/<id>/snapshot.png -H "X-API-Token: $TOKEN" -o snap.png
curl -X DELETE localhost:8600/desktop/session/<id> -H "X-API-Token: $TOKEN"
```

Security model:
- VNC binds to `127.0.0.1` only; the browser reaches it exclusively through the
  noVNC websocket gateway.
- Every session gets its own display number, VNC port and noVNC port (isolation).
- All management endpoints require `X-API-Token`; unauthorized → 401.
- `DELETE` stops the session and releases display/port slots (resource cleanup).

## Operations

```bash
hsaai-ctl status          # table of all 7 services + endpoints
hsaai-ctl restart all
hsaai-ctl stop all        # graceful, ordered shutdown
```

Logs: `$HSAOI_LOGS` (default `runtime/logs/`) — one file per service.
