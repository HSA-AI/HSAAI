#!/usr/bin/env python3
"""test-desktop-input.py — REAL end-to-end remote desktop input verification.

Chain tested: vncdotool (VNC client) -> x11vnc -> Xvfb :99 -> xterm -> shell
Success criteria: typed command executes and creates a real file on disk.
"""
import time
import os
from vncdotool import api

VNC_HOST = "127.0.0.1"
VNC_PORT = 5999
PASSWORD = "HsaaiDesktop_2026"
_RUNTIME = os.environ.get("HSAAI_RUNTIME", "/home/z/my-project/runtime")
MARKER_FILE = os.path.join(_RUNTIME, "desktop_input_test.txt")

if os.path.exists(MARKER_FILE):
    os.remove(MARKER_FILE)

print("[1] connecting to VNC server...")
client = api.connect(f"{VNC_HOST}::{VNC_PORT}", password=PASSWORD)
print("    connected OK")

result = "FAIL"
try:
    print("[2] capturing screen BEFORE input...")
    client.captureScreen(os.path.join(_RUNTIME, "logs", "desktop-before.png"))

    print("[3] mouse: moving + clicking into terminal area (200,150)...")
    client.mouseMove(200, 150)
    time.sleep(0.5)
    client.mousePress(1)
    time.sleep(0.5)

    print("[4] keyboard: typing test command...")
    for ch in f"echo DESKTOP_INPUT_OK > {MARKER_FILE}\n":
        client.keyPress(ch if ch != "\n" else "return")
        time.sleep(0.05)

    print("[5] waiting for shell execution...")
    time.sleep(2)

    print("[6] capturing screen AFTER input...")
    client.captureScreen(os.path.join(_RUNTIME, "logs", "desktop-after.png"))

    exists = os.path.exists(MARKER_FILE)
    content = open(MARKER_FILE).read().strip() if exists else ""
    before = os.path.getsize(os.path.join(_RUNTIME, "logs", "desktop-before.png"))
    after = os.path.getsize(os.path.join(_RUNTIME, "logs", "desktop-after.png"))

    print()
    print("=" * 52)
    print(f"keyboard -> file created : {'PASS' if exists else 'FAIL'}")
    print(f"file content             : '{content}'")
    print(f"screen streamed          : {before} -> {after} bytes")
    print("=" * 52)
    result = "PASS" if exists and content == "DESKTOP_INPUT_OK" else "FAIL"
finally:
    # NOTE: vncdotool api.connect() cleanup can hang; use low-level terminate.
    try:
        client.connection.disconnect()
    except Exception:
        pass
    try:
        client.terminate()
    except Exception:
        pass
    print("RESULT:", result)
    os._exit(0)  # hard-exit avoids lingering client threads
