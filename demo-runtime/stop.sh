#!/usr/bin/env bash
# HSAAI Demo Runtime — stop all dockerless demo processes
RUNTIME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for name in web backend mock-keycloak; do
  pidfile="$RUNTIME_DIR/$name.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && echo "stopped $name (pid $pid)"
    fi
    rm -f "$pidfile"
  fi
done

# Clean up any stragglers bound to the demo ports
for port in 3000 8080 9080; do
  pids="$(lsof -t -i tcp:$port 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null && echo "freed port $port"
done
echo "done."
