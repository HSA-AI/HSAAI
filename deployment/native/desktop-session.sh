#!/usr/bin/env bash
# desktop-session.sh (v3, portable) — Start/Stop a REAL remote Linux desktop session
# Chain: Xvfb (X server) -> openbox (WM) -> xterm/xapps -> x11vnc -> websockify (noVNC)
# FFmpeg is used for screen capture snapshots (x11grab).
set -euo pipefail
_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_SELF_DIR/hsaai-env.sh"

SESSION_ID="${1:-default}"
ACTION="${2:-start}"

BASE="$RUNTIME"
SESS=$BASE/desktop/$SESSION_ID
PIDDIR=$SESS/pids
LOGS=$BASE/logs/desktop-$SESSION_ID
GEOM="${HSAAI_DESKTOP_GEOM:-1440x900x24}"
DISPLAY_NUM="${HSAAI_DESKTOP_DISPLAY:-99}"
VNC_PORT="${HSAAI_VNC_PORT:-5999}"
NOVNC_PORT="${HSAAI_NOVNC_PORT:-6080}"
export DISPLAY=":$DISPLAY_NUM"
export XDG_DATA_DIRS=$ROOTFS/usr/share
export XDG_CONFIG_DIRS=$ROOTFS/etc/xdg
export XDG_CONFIG_HOME=$SESS/xdg
mkdir -p "$XDG_CONFIG_HOME/openbox"

# Custom openbox menu + config (real applications menu)
cat > "$XDG_CONFIG_HOME/openbox/menu.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_menu>
  <menu id="root-menu" label="HSAAI Desktop">
    <item label="Terminal"><action name="Execute"><command>xterm</command></action></item>
    <item label="Clock"><action name="Execute"><command>xclock</command></action></item>
    <item label="Calculator"><action name="Execute"><command>xcalc</command></action></item>
    <item label="Eyes"><action name="Execute"><command>xeyes</command></action></item>
    <separator/>
    <item label="Reconfigure WM"><action name="Reconfigure"/></item>
    <item label="Exit Session"><action name="Exit"/></item>
  </menu>
</openbox_menu>
EOF
cat > "$XDG_CONFIG_HOME/openbox/rc.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <theme><name>Clearlooks</name></theme>
  <keyboard><keybind key="W-t"><action name="Execute"><command>xterm</command></action></keybind></keyboard>
</openbox_config>
EOF

write_pid() { echo "$2" > "$PIDDIR/$1.pid"; }
mkdir -p "$PIDDIR" "$LOGS" "$SESS/home"
is_running() { [ -f "$PIDDIR/$1.pid" ] && kill -0 "$(cat "$PIDDIR/$1.pid")" 2>/dev/null; }

stop_session() {
  for p in novnc x11vnc apps wm xvfb; do
    if is_running "$p"; then
      kill "$(cat "$PIDDIR/$p.pid")" 2>/dev/null || true
    fi
    rm -f "$PIDDIR/$p.pid"
  done
  echo "[$SESSION_ID] session stopped"
}

if [ "$ACTION" = "stop" ]; then stop_session; exit 0; fi
if [ "$ACTION" = "restart" ]; then stop_session; sleep 1; fi

# Already running?
if is_running xvfb; then echo "[$SESSION_ID] already running"; exit 0; fi

# Clean stale X11 locks from previous (unclean) runs
rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}" 2>/dev/null || true
# Kill leftovers of this session id that were not tracked by piddir
pkill -f "Xvfb :${DISPLAY_NUM} " 2>/dev/null || true

# 1) Xvfb — virtual X server (the existing binary)
Xvfb :$DISPLAY_NUM -screen 0 "$GEOM" -nolisten tcp \
  -auth "$SESS/.Xauth" > "$LOGS/xvfb.log" 2>&1 &
write_pid xvfb $!
sleep 1

# 2) Window manager — openbox (real WM)
DISPLAY=":$DISPLAY_NUM" XAUTHORITY="$SESS/.Xauth" \
  "$ROOTFS/usr/bin/openbox" > "$LOGS/openbox.log" 2>&1 &
write_pid wm $!
sleep 1

# 3) GUI applications — real X11 apps (terminal, clock, calculator, eyes)
# NOTE: the whole subshell redirects its output to the log so that no child
# process keeps the caller's stdout/stderr pipes open (breaks subprocess.run).
(
  export DISPLAY=":$DISPLAY_NUM" XAUTHORITY="$SESS/.Xauth" HOME="$SESS/home"
  "$ROOTFS/usr/bin/xterm" -geometry 100x30+60+60 -title "HSAAI Terminal" -bg black -fg green &
  "$ROOTFS/usr/bin/xclock" -geometry 300x300+850+80 &
  "$ROOTFS/usr/bin/xcalc" -geometry +850+420 &
  wait
) > "$LOGS/apps.log" 2>&1 &
write_pid apps $!

# 4) x11vnc — expose the X display via VNC (localhost only; security)
"$ROOTFS/usr/bin/x11vnc" -display :$DISPLAY_NUM -auth "$SESS/.Xauth" \
  -rfbport "$VNC_PORT" -localhost -forever -shared -noxrecord -noxfixes -noxdamage \
  -passwd "HsaaiDesktop_2026" > "$LOGS/x11vnc.log" 2>&1 &
write_pid x11vnc $!
sleep 2

# 5) noVNC websocket gateway — browser access
"$RUNTIME/venv-desktop/bin/websockify" \
  --web="$RUNTIME/noVNC" 0.0.0.0:"$NOVNC_PORT" localhost:"$VNC_PORT" \
  > "$LOGS/novnc.log" 2>&1 &
write_pid novnc $!
sleep 1

echo "[$SESSION_ID] session started: display=:$DISPLAY_NUM vnc=$VNC_PORT novnc=$NOVNC_PORT"
