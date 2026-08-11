#!/usr/bin/env python3
"""
reset_status.py

Reset translation_status entri tertentu kembali ke "pending", supaya
bisa diterjemahkan ulang oleh translate_id.py. Berguna saat:
  - Uji coba terjemahan menghasilkan kualitas buruk dan mau dicoba ulang
  - Prompt/translation_rules.yaml berubah, dan entri lama perlu
    diterjemahkan ulang dengan aturan baru (lihat README > "Alur
    Terjemahan": perubahan rules tidak otomatis berlaku surut)

TIGA MODE (pilih salah satu):

  1. --strong-numbers H1,H2,H3
     Reset nomor Strong tertentu saja (dipisah koma, tanpa spasi).

  2. --all-machine
     Reset SEMUA entri berstatus "machine" kembali ke "pending".
     TIDAK menyentuh entri "reviewed" atau "official-sabda" (itu
     sudah ditinjau manusia, sengaja dilindungi dari ketimpa ulang).

  3. --all
     Reset SEMUA entri (termasuk yang "reviewed"/"official-sabda")
     kembali ke "pending". PAKAI HATI-HATI -- ini juga menghapus hasil
     tinjauan manual. Akan minta konfirmasi ketik "yes" sebelum jalan.

Penggunaan:
    python scripts/reset_status.py --input data/hebrew/strongs-hebrew.json --strong-numbers H1,H2,H3,H4,H5
    python scripts/reset_status.py --input data/hebrew/strongs-hebrew.json --all-machine
    python scripts/reset_status.py --input data/hebrew/strongs-hebrew.json --all
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--strong-numbers", help="Daftar nomor Strong dipisah koma, mis. H1,H2,H3")
    mode.add_argument("--all-machine", action="store_true", help="Reset semua entri berstatus 'machine' saja")
    mode.add_argument("--all", action="store_true", help="Reset SEMUA entri termasuk yang sudah 'reviewed' (minta konfirmasi)")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"File tidak ditemukan: {args.input}")

    with args.input.open(encoding="utf-8") as f:
        data = json.load(f)

    if args.strong_numbers:
        targets = {s.strip().upper() for s in args.strong_numbers.split(",") if s.strip()}
        matcher = lambda e: e["strong_number"].upper() in targets
        label = f"{len(targets)} nomor Strong yang diminta"

    elif args.all_machine:
        matcher = lambda e: e.get("translation_status") == "machine"
        label = "semua entri berstatus 'machine'"

    else:  # --all
        n_reviewed = sum(1 for e in data if e.get("translation_status") in ("reviewed", "official-sabda"))
        print(f"PERINGATAN: --all akan reset SEMUA entri, termasuk {n_reviewed} entri yang "
              f"sudah 'reviewed'/'official-sabda' (hasil tinjauan manual akan hilang).")
        confirm = input("Ketik 'yes' untuk lanjut: ").strip().lower()
        if confirm != "yes":
            print("Dibatalkan.")
            return
        matcher = lambda e: True
        label = "SEMUA entri"

    reset_count = 0
    not_found = set(args.strong_numbers.split(",")) if args.strong_numbers else set()
    for e in data:
        if matcher(e):
            e["definition"]["id"] = None
            e["translation_status"] = "pending"
            reset_count += 1
            not_found.discard(e["strong_number"])
            not_found.discard(e["strong_number"].upper())
            not_found.discard(e["strong_number"].lower())

    with args.input.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] {reset_count} entri ({label}) direset ke 'pending' di {args.input}")
    if args.strong_numbers and not_found:
        print(f"[WARN] Nomor Strong tidak ditemukan di file ini: {', '.join(sorted(not_found))}")


if __name__ == "__main__":
    main()