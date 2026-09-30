#!/usr/bin/env python3
"""Create a clean HSAAI delivery archive with SHA-256 verification.

The source workspace is never deleted or modified except for generated release
manifest files. Existing output archives are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_PARTS = {
    ".git",
    "node_modules",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "coverage_html",
    "site-packages",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".tsbuildinfo",
}

EXCLUDE_ROOTS = {
    "data",
    "backups",
    "pytest-of-root",
}

EXCLUDE_PREFIXES = (
    "services/data/",
    "tmp/",
)

EXCLUDE_EXACT = {
    ".coverage",
    "tests/coverage.xml",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def excluded_name(name: str) -> bool:
    relative = Path(name)

    if not relative.parts:
        return True

    if any(part in EXCLUDE_PARTS for part in relative.parts):
        return True

    if relative.suffix.lower() in EXCLUDE_SUFFIXES:
        return True

    if name in EXCLUDE_EXACT:
        return True

    if relative.parts[0] in EXCLUDE_ROOTS:
        return True

    if name.startswith(EXCLUDE_PREFIXES):
        return True

    if relative.parts[0].startswith(("pip-", "tmp")):
        return True

    lower = relative.name.lower()

    if relative.name.startswith(".env") and not any(
        token in lower for token in ("example", "sample", "template")
    ):
        return True

    return False


def archive_files(path: str | Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if not name.endswith("/")
        ]

        if not names:
            return {}

        root = names[0].split("/", 1)[0]
        prefix = f"{root}/"

        if not all(name.startswith(prefix) for name in names):
            prefix = ""

        return {
            name[len(prefix):]: sha(archive.read(name))
            for name in names
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output).resolve()

    if output.exists():
        parser.error(
            "Output already exists; choose a new output to preserve it"
        )

    original = archive_files(args.original)

    checkpoint = (
        archive_files(args.checkpoint)
        if args.checkpoint
        else {}
    )

    original_required = {
        name
        for name in original
        if not excluded_name(name)
    }

    checkpoint_required = {
        name
        for name in checkpoint
        if not excluded_name(name)
    }

    required = original_required | checkpoint_required

    missing = [
        name
        for name in sorted(required)
        if not (ROOT / name).is_file()
    ]

    if missing:
        raise RuntimeError(
            "Missing prior package-eligible files: " + repr(missing)
        )

    manifest = ROOT / "docs/release/SOURCE_CHANGES.json"
    sums = ROOT / "SHA256SUMS.txt"

    included: list[Path] = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue

        relative = path.relative_to(ROOT)
        name = relative.as_posix()

        if path in {manifest, sums}:
            continue

        if excluded_name(name):
            continue

        included.append(path)

    current = {
        path.relative_to(ROOT).as_posix(): sha(path.read_bytes())
        for path in included
    }

    result = {
        "original_archive_sha256": sha(
            Path(args.original).read_bytes()
        ),
        "original_file_count": len(original),
        "original_package_eligible_count": len(original_required),
        "original_files_excluded_by_policy": sorted(
            set(original) - original_required
        ),
        "original_files_missing": [],
        "original_files_unchanged": [
            name
            for name in sorted(original_required)
            if current.get(name) == original[name]
        ],
        "original_files_modified": [
            name
            for name in sorted(original_required)
            if current.get(name) != original[name]
        ],
        "added_files": sorted(
            set(current) - set(original_required)
        ),
        "checkpoint_file_count": len(checkpoint),
        "checkpoint_package_eligible_count": len(
            checkpoint_required
        ),
        "checkpoint_files_missing": [],
        "packaging_policy": (
            "Package-eligible source files are preserved. "
            "Git metadata, dependency/build caches, runtime/test "
            "databases and logs, private environment files, "
            "temporary data and generated runtime state are excluded."
        ),
    }

    manifest.parent.mkdir(parents=True, exist_ok=True)

    manifest.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    included.append(manifest)

    sums.write_text(
        "".join(
            sha(path.read_bytes())
            + "  "
            + path.relative_to(ROOT).as_posix()
            + "\n"
            for path in sorted(included)
        ),
        encoding="utf-8",
    )

    included.append(sums)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(
        output,
        "x",
        zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(included):
            archive.write(
                path,
                "HSAAI/"
                + path.relative_to(ROOT).as_posix(),
            )

    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None, "ZIP CRC failure"

        for line in archive.read(
            "HSAAI/SHA256SUMS.txt"
        ).decode().splitlines():
            digest, name = line.split("  ", 1)

            assert (
                sha(archive.read("HSAAI/" + name))
                == digest
            ), "Hash mismatch: " + name

        missing_required = [
            name
            for name in sorted(required)
            if "HSAAI/" + name not in archive.namelist()
        ]

        assert not missing_required, (
            "Missing required package files: "
            + repr(missing_required)
        )

        forbidden = [
            name
            for name in archive.namelist()
            if name.startswith("HSAAI/")
            and excluded_name(name[len("HSAAI/"):])
        ]

        assert not forbidden, (
            "Forbidden package files: " + repr(forbidden)
        )

    report = {
        "file": str(output),
        "size_bytes": output.stat().st_size,
        "sha256": sha(output.read_bytes()),
        "files": len(included),
        "original_files_preserved": len(
            original_required
        ),
        "original_files_excluded_by_policy": len(
            set(original) - original_required
        ),
        "checkpoint_files_preserved": len(
            checkpoint_required
        ),
        "zip_crc": "passed",
        "file_hashes": "passed",
        "package_hygiene": "passed",
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
