from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
page = ROOT / "apps" / "web" / "app" / "page.tsx"
text = page.read_text(encoding="utf-8")
checks = {
    "home page exists": page.exists(),
    "assistant label exists": "المساعد الذكي" in text,
    "new chat href exists": "/chat?new=1" in text,
    "header assistant button exists": "فتح المساعد الذكي وبدء محادثة جديدة" in text,
    "hero assistant button exists": "فتح المساعد الذكي" in text,
    "mobile floating assistant button exists": "الزر العائم" in text or "fixed bottom-5" in text,
    "brand colors preserved": "hsa-yellow" in text and "hsa-black" in text and "hsa-gold" in text,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print("Home assistant button audit: FAILED")
    for name in failed:
        print(f"- {name}")
    raise SystemExit(1)
print("Home assistant button audit: OK")
