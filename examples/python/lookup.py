"""
Contoh: cari satu entri Strong's berdasarkan nomornya.
Jalankan: python lookup.py H430
"""

import json
import sys
from pathlib import Path

DICTIONARY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "combined" / "strongs-full.json"


def load_dictionary() -> list[dict]:
    with DICTIONARY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def lookup(strong_number: str, dictionary: list[dict]) -> dict | None:
    return next((e for e in dictionary if e["strong_number"] == strong_number), None)


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "H430"
    entry = lookup(query, load_dictionary())

    if entry is None:
        print(f"Nomor Strong '{query}' tidak ditemukan.")
        sys.exit(1)

    print(json.dumps(entry, indent=2, ensure_ascii=False))
