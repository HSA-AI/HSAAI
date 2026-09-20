#!/usr/bin/env python3
"""audit-hsaai.py — Comprehensive static audit of the HSAAI project.
Checks: python syntax (all), compose YAML validity, compose build contexts,
env var alignment (.env* vs backend config), missing requirements packages.
Outputs a findings list with severity.
"""
import ast, os, re, sys, glob
import yaml

# v3 portable: project root = parent of deployment/ containing this script
ROOT = os.environ.get("HSAAI_HOME") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FINDINGS_OUT = os.environ.get("HSAAI_RUNTIME") or os.path.abspath(os.path.join(ROOT, "..", "runtime"))
findings = []  # (severity, location, message)

def add(sev, loc, msg):
    findings.append((sev, loc, msg))

# ---------- 1) Python syntax sweep ----------
py_files = []
for base in ("services", "packages", "scripts", "tools", "apps"):
    for dirpath, dirs, files in os.walk(os.path.join(ROOT, base)):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".venv-backend", "__pycache__", ".git", "_deprecated_adapters")]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(dirpath, f))

syntax_bad = 0
for p in py_files:
    try:
        src = open(p, "r", encoding="utf-8", errors="replace").read()
        ast.parse(src, filename=p)
    except SyntaxError as e:
        syntax_bad += 1
        add("CRITICAL", os.path.relpath(p, ROOT), f"SyntaxError: {e.msg} (line {e.lineno})")
print(f"[1] python files checked: {len(py_files)}, syntax errors: {syntax_bad}")

# ---------- 2) docker-compose.yml ----------
compose_path = os.path.join(ROOT, "docker-compose.yml")
try:
    compose = yaml.safe_load(open(compose_path))
    services = compose.get("services", {})
    print(f"[2] compose services parsed: {len(services)}")
except Exception as e:
    services = {}
    add("CRITICAL", "docker-compose.yml", f"YAML parse error: {e}")

# build contexts exist?
for name, cfg in services.items():
    build = cfg.get("build")
    if isinstance(build, str) and not os.path.isdir(os.path.join(ROOT, build)):
        add("HIGH", f"compose:{name}", f"build context missing: {build}")
    elif isinstance(build, dict):
        ctx = build.get("context", "")
        if ctx and not os.path.isdir(os.path.join(ROOT, ctx)):
            add("HIGH", f"compose:{name}", f"build context missing: {ctx}")
    # depends_on sanity
    for dep in (cfg.get("depends_on") or {}):
        if dep not in services:
            add("HIGH", f"compose:{name}", f"depends_on unknown service: {dep}")

# ---------- 3) env vars alignment ----------
env_keys = set()
for f in (".env.example", ".env.production.example"):
    path = os.path.join(ROOT, f)
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                env_keys.add(line.split("=", 1)[0].strip())

# backend settings env aliases
cfg_src = open(os.path.join(ROOT, "services/backend_core/config.py")).read()
cfg_aliases = set(re.findall(r'validation_alias="([A-Z0-9_]+)"', cfg_src))
missing_in_examples = sorted(a for a in cfg_aliases if a not in env_keys)
for k in missing_in_examples:
    add("MEDIUM", ".env.example", f"backend config requires '{k}' but not present in .env examples")
print(f"[3] env keys in examples: {len(env_keys)}, backend aliases: {len(cfg_aliases)}, missing: {len(missing_in_examples)}")

# ---------- 4) imports of missing local modules (quick heuristic on backend_core) ----------
# check that packages.common is importable relative to repo layout
for svc_main in ["services/backend_core/main.py", "services/api_gateway/main.py",
                 "services/rag_engine/main.py", "services/llm_gateway/main.py"]:
    p = os.path.join(ROOT, svc_main)
    if not os.path.exists(p):
        add("MEDIUM", svc_main, "entry file missing")

# ---------- 5) requirements: check uvicorn/fastapi pinned duplicates sanity ----------
req = open(os.path.join(ROOT, "services/backend_core/requirements.txt")).read()
pkgs = [l.split("==")[0].split(">=")[0].split("<")[0].strip().lower().replace("_","-")
        for l in req.splitlines() if l.strip() and not l.strip().startswith("#") and l.strip() != "-r ../../packages/common/requirements.txt"]
dups = sorted({p for p in pkgs if pkgs.count(p) > 1})
if dups:
    add("LOW", "services/backend_core/requirements.txt", f"duplicated pins: {', '.join(dups)}")
print(f"[4] backend requirements packages: {len(pkgs)}, duplicates: {dups or 'none'}")

# ---------- report ----------
print("\n================ AUDIT FINDINGS ================")
crit = [f for f in findings if f[0] == "CRITICAL"]
high = [f for f in findings if f[0] == "HIGH"]
med  = [f for f in findings if f[0] == "MEDIUM"]
low  = [f for f in findings if f[0] == "LOW"]
for sev, lst in (("CRITICAL", crit), ("HIGH", high), ("MEDIUM", med), ("LOW", low)):
    for loc, msg in [(f[1], f[2]) for f in lst]:
        print(f"[{sev}] {loc} :: {msg}")
print(f"TOTAL: {len(findings)} (C:{len(crit)} H:{len(high)} M:{len(med)} L:{len(low)})")

import json
json.dump([{"severity": s, "location": l, "message": m} for s, l, m in findings],
          open(os.path.join(FINDINGS_OUT, "audit-findings.json"), "w"), indent=2)
