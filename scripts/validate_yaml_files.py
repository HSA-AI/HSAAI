#!/usr/bin/env python3
from pathlib import Path
import sys
try:
    import yaml
except Exception as exc:
    print(f"PyYAML is required for YAML validation: {exc}")
    sys.exit(1)

errors = []
for path in list(Path('.').rglob('*.yml')) + list(Path('.').rglob('*.yaml')):
    if any(part in {'.git', '.pytest_cache', 'node_modules'} for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8')
        list(yaml.safe_load_all(text))
    except Exception as exc:
        errors.append((str(path), str(exc)))

if errors:
    for p, e in errors:
        print(f"YAML_ERROR {p}: {e}")
    sys.exit(1)
print("YAML validation: OK")
