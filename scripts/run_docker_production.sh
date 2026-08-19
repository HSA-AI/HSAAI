#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
