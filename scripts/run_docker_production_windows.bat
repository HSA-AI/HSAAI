@echo off
cd /d %~dp0
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
pause
