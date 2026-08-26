# HSAAI Governance Service — Production Docker Image
# RBAC + ABAC + Audit + Data Governance + Compliance
#
# FIX CRITICAL-4 (HSAAI-DEP-2026-07-11): Previously this Dockerfile copied
# only `main.py` to /app and ran `uvicorn main:app` with `PYTHONPATH=/app`.
# That worked for the bare `main.py`, but `governance/main.py` imports from
# `backend_core.*` (e.g. for shared audit / RBAC types), which requires the
# project-root layout. Now we mirror the api_gateway pattern: copy the whole
# service folder, plus `packages/common`, and set PYTHONPATH to /app so the
# package-style imports resolve correctly. An `__init__.py` is also created
# so `governance` is treated as a proper Python package.
FROM python:3.12-slim AS builder
WORKDIR /app
# Copy the service requirements AND the shared packages/common/requirements.txt
# (referenced via `-r` from the service file) so pip can resolve the
# consolidated shared dependencies.
COPY services/governance/requirements.txt ./services/governance/requirements.txt
COPY packages/common/requirements.txt ./packages/common/requirements.txt
RUN pip install --no-cache-dir --user -r ./services/governance/requirements.txt

FROM python:3.12-slim
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
# FIX CRITICAL-4: copy the entire governance service folder (not just main.py)
# so that __init__.py, sibling modules, and any sub-packages are present.
COPY services/governance /app/governance
COPY packages/common /app/packages/common
# Ensure governance is importable as a package (the source tree may not
# always ship with __init__.py — create it defensively).
RUN touch /app/governance/__init__.py
ENV PYTHONPATH=/app
RUN chown -R appuser:appuser /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
WORKDIR /app/governance
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8011/health')" || exit 1
EXPOSE 8011
# Run from inside /app/governance so `main:app` resolves, while PYTHONPATH=/app
# keeps `governance.*` and `packages.common.*` imports working for callers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011", "--workers", "2"]
