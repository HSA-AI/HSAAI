#!/usr/bin/env bash
set -e
printf "Node: "; node -v
printf "NPM: "; npm -v
printf "Python: "; python --version || python3 --version
printf "Docker: "; docker --version
printf "Docker Compose: "; docker compose version
