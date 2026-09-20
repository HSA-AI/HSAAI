#!/bin/bash
set -e
echo "Docker:"
docker version
echo "Compose:"
docker compose version
echo "Compose validation:"
docker compose config >/dev/null
echo "OK"
