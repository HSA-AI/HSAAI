#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
checks = {
    "assistant_first_home": ROOT / "apps/web/app/page.tsx",
    "simplified_sidebar": ROOT / "apps/web/components/layout/sidebar.tsx",
    "mobile_bottom_nav": ROOT / "apps/web/components/layout/mobile-bottom-nav.tsx",
    "topbar_new_chat": ROOT / "apps/web/components/layout/topbar.tsx",
}

required = {
    "apps/web/app/page.tsx": ["كيف يمكنني مساعدتك اليوم؟", "/chat?new=1", "Quick Actions", "Main Navigation"],
    "apps/web/components/layout/sidebar.tsx": ["المساعد", "المعرفة", "البحث", "لوحة القيادة", "الإعدادات", "الإدارة"],
    "apps/web/components/layout/mobile-bottom-nav.tsx": ["/chat?new=1", "المعرفة", "البحث"],
    "apps/web/components/layout/topbar.tsx": ["محادثة جديدة", "HSAAI — المساعد الذكي المؤسسي"],
}

errors = []
for label, path in checks.items():
    if not path.exists():
        errors.append(f"Missing {label}: {path}")

for rel, tokens in required.items():
    path = ROOT / rel
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            errors.append(f"Missing token '{token}' in {rel}")

if errors:
    print("Enterprise UX audit: FAILED")
    for e in errors:
        print("-", e)
    raise SystemExit(1)

print("Enterprise UX audit: OK")
print("Assistant-first home, simplified navigation, mobile navigation, and official HSAAI brand structure are present.")
