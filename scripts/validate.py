#!/usr/bin/env python3
"""
validate.py

Memvalidasi setiap file dataset di data/**/*.json terhadap
schema/strongs.schema.json. Dipakai secara lokal maupun di CI
(.github/workflows/ci.yml).

Penggunaan:
    python scripts/validate.py
    python scripts/validate.py --file data/hebrew/strongs-hebrew.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator
except ImportError:
    sys.exit(
        "Dependensi 'jsonschema' belum terpasang. Jalankan: pip install jsonschema --break-system-packages"
    )

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "strongs.schema.json"


def load_schema():
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def validate_file(path: Path, validator: Draft7Validator) -> int:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"[FAIL] {path}: root harus berupa array/list")
        return 1

    error_count = 0
    seen_numbers = set()
    for i, entry in enumerate(data):
        errors = sorted(validator.iter_errors(entry), key=lambda e: e.path)
        for err in errors:
            error_count += 1
            print(f"[FAIL] {path} entri[{i}] ({entry.get('strong_number', '?')}): {err.message}")

        sn = entry.get("strong_number")
        if sn:
            if sn in seen_numbers:
                error_count += 1
                print(f"[FAIL] {path} entri[{i}]: strong_number duplikat -> {sn}")
            seen_numbers.add(sn)

    if error_count == 0:
        print(f"[OK] {path}: {len(data)} entri valid")
    return error_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=None, help="Validasi satu file saja")
    args = parser.parse_args()

    schema = load_schema()
    validator = Draft7Validator(schema)

    if args.file:
        files = [args.file]
    else:
        files = sorted(f for f in (ROOT / "data").rglob("*.json") if f.name != "stats.json")

    if not files:
        print("Tidak ada file JSON ditemukan di data/. Lewati validasi.")
        sys.exit(0)

    total_errors = 0
    for f in files:
        total_errors += validate_file(f, validator)

    if total_errors:
        print(f"\n{total_errors} error ditemukan.")
        sys.exit(1)
    print("\nSemua file dataset valid.")


if __name__ == "__main__":
    main()
