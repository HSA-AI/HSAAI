from __future__ import annotations
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"
REQUIRED_FILES = [
    WEB / "public" / "hsaai_official_logo.png",
    WEB / "public" / "brand" / "hsa-logo.jpg",
    WEB / "public" / "brand" / "hsaai-assistant-circle.png",
]
REQUIRED_TOKENS = ["hsa-yellow", "hsa-black", "hsa-gold", "enterprise-slate", "hsa-soft"]
ALLOWED_HEX_FILES = {
    "apps/web/tailwind.config.ts",
    "apps/web/styles/globals.css",
    "apps/web/lib/brand.ts",
    "apps/web/app/layout.tsx",
}
FORBIDDEN_STYLE_TERMS = ["cyan", "emerald", "#F1BC38", "#111827"]
SCAN_DIRS = [WEB / "app", WEB / "components", WEB / "lib", WEB / "styles"]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for file in REQUIRED_FILES:
        if not file.exists():
            errors.append(f"Missing brand asset: {rel(file)}")

    tailwind = read(WEB / "tailwind.config.ts") if (WEB / "tailwind.config.ts").exists() else ""
    globals_css = read(WEB / "styles" / "globals.css") if (WEB / "styles" / "globals.css").exists() else ""
    brand_ts = read(WEB / "lib" / "brand.ts") if (WEB / "lib" / "brand.ts").exists() else ""

    for token in REQUIRED_TOKENS:
        if token not in tailwind and token not in globals_css:
            errors.append(f"Missing design token: {token}")

    if "/hsaai_official_logo.png" not in brand_ts:
        errors.append("brand.logoPath must point to /hsaai_official_logo.png")

    for base in SCAN_DIRS:
        for file in base.rglob("*.tsx"):
            text = read(file)
            for term in FORBIDDEN_STYLE_TERMS:
                if term in text:
                    errors.append(f"Off-brand style term '{term}' found in {rel(file)}")
            for hex_value in re.findall(r"#[0-9A-Fa-f]{6}", text):
                if rel(file) not in ALLOWED_HEX_FILES:
                    warnings.append(f"Hard-coded hex {hex_value} in {rel(file)}")

    print("HSAAI Brand Identity Audit")
    print("=" * 28)
    print(f"Required assets checked: {len(REQUIRED_FILES)}")
    print(f"Required tokens checked: {len(REQUIRED_TOKENS)}")
    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"- {item}")
    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("\nResult: OK — official logo and HSA brand tokens are preserved.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
