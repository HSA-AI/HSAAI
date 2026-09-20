from pathlib import Path
root = Path(__file__).resolve().parents[2]
required = [
    root / "apps/web/public/brand/hsaai-assistant-circle.png",
    root / "apps/web/app/page.tsx",
    root / "apps/web/components/layout/sidebar.tsx",
    root / "apps/web/components/layout/mobile-bottom-nav.tsx",
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing assistant icon integration files: " + ", ".join(missing))
content = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in required if p.suffix in {".tsx", ".ts"})
if "brand.assistant.iconPath" not in content or "/chat?new=1" not in content:
    raise SystemExit("Assistant icon button integration incomplete")
print("Assistant official icon audit: OK")
