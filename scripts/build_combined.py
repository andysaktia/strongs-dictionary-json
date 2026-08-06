#!/usr/bin/env python3
"""
build_combined.py

Menggabungkan data/hebrew/strongs-hebrew.json + data/greek/strongs-greek.json
menjadi satu file data/combined/strongs-full.json, sekaligus menghasilkan
statistik ringkas untuk README (jumlah entri, persentase status terjemahan).

Penggunaan:
    python scripts/build_combined.py
"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEBREW = ROOT / "data" / "hebrew" / "strongs-hebrew.json"
GREEK = ROOT / "data" / "greek" / "strongs-greek.json"
OUTPUT = ROOT / "data" / "combined" / "strongs-full.json"
STATS_OUTPUT = ROOT / "data" / "combined" / "stats.json"


def load(path: Path) -> list:
    if not path.exists():
        print(f"[SKIP] {path} belum ada")
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main():
    hebrew = load(HEBREW)
    greek = load(GREEK)
    combined = hebrew + greek

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    status_counts = Counter(e.get("translation_status", "unknown") for e in combined)
    stats = {
        "total_entries": len(combined),
        "hebrew_entries": len(hebrew),
        "greek_entries": len(greek),
        "translation_status_breakdown": dict(status_counts),
    }
    with STATS_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"[OK] {len(combined)} entri digabung -> {OUTPUT}")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
