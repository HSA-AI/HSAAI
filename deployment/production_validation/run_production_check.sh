#!/bin/bash
set -e
docker compose up -d
docker compose ps
echo "Check logs with: docker compose logs -f"
