#!/usr/bin/env python3
"""
translate_id.py

Mengisi kolom definition.id secara batch menggunakan Anthropic API,
lalu menandai translation_status="machine". Entri yang sudah
berstatus "reviewed" atau "official-sabda" TIDAK akan ditimpa.

Wajib set environment variable ANTHROPIC_API_KEY sebelum menjalankan.

Penggunaan:
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/translate_id.py --input data/hebrew/strongs-hebrew.json --limit 50

Aturan terjemahan (istilah yang wajib dipertahankan/dilarang, dll) dibaca
dari scripts/translation_rules.yaml -- edit file itu untuk mengubah
perilaku terjemahan tanpa menyentuh kode ini. Gunakan --rules untuk
menunjuk file rules lain.

Catatan desain (lihat README > "Alur Terjemahan"):
    - Berjalan secara batch kecil (default 20 entri/panggilan) supaya
      mudah diaudit dan dihentikan/diulang tanpa kehilangan progres.
    - Selalu tulis ulang file output setelah setiap batch (resume-safe).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit(
        "Dependensi 'anthropic' belum terpasang. Jalankan: pip install anthropic --break-system-packages"
    )

try:
    import yaml
except ImportError:
    sys.exit(
        "Dependensi 'pyyaml' belum terpasang. Jalankan: pip install pyyaml --break-system-packages"
    )

MODEL = "claude-sonnet-4-6"

DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "translation_rules.yaml"

BASE_SYSTEM_PROMPT = (
    "Anda adalah penerjemah ahli untuk istilah teologis Ibrani dan Yunani "
    "dari Strong's Dictionary ke Bahasa Indonesia. Terjemahkan definisi "
    "berikut secara ringkas dan akurat, konsisten dengan istilah yang "
    "lazim dipakai Alkitab terjemahan Indonesia (LAI/TB). Jangan "
    "menambahkan penjelasan lain, kembalikan HANYA teks terjemahan."
)


def load_rules(rules_path: Path) -> dict:
    if not rules_path.exists():
        print(f"[WARN] File rules {rules_path} tidak ditemukan, lanjut tanpa aturan khusus.")
        return {}
    with rules_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_system_prompt(rules: dict) -> str:
    """Gabungkan prompt dasar + aturan dari translation_rules.yaml."""
    parts = [BASE_SYSTEM_PROMPT]

    preserve = rules.get("preserve_terms") or []
    if preserve:
        parts.append("\nATURAN WAJIB -- Istilah berikut TIDAK BOLEH diterjemahkan, "
                      "pertahankan bentuk transliterasi aslinya persis seperti ini:")
        for item in preserve:
            term = item.get("term", "")
            note = item.get("note", "")
            parts.append(f"- \"{term}\"{f' -- {note}' if note else ''}")

    forbidden = rules.get("forbidden_terms") or []
    if forbidden:
        parts.append("\nATURAN WAJIB -- Kata/istilah berikut DILARANG dipakai dalam hasil terjemahan:")
        for item in forbidden:
            term = item.get("term", "")
            reason = item.get("reason", "")
            parts.append(f"- \"{term}\"{f' -- {reason}' if reason else ''}")

    guidelines = rules.get("general_guidelines") or []
    if guidelines:
        parts.append("\nPanduan tambahan:")
        for g in guidelines:
            parts.append(f"- {g}")

    return "\n".join(parts)


def translate_batch(client: "anthropic.Anthropic", texts: list[str], lemmas: list[str], system_prompt: str) -> list[str]:
    # Sertakan lemma (kata asli) di samping definisi EN, supaya model tahu
    # persis kata apa yang sedang diterjemahkan -- penting untuk mengecek
    # apakah entri ini termasuk nama/atribut Tuhan yang wajib dipertahankan.
    numbered = "\n".join(
        f"{i+1}. [lemma: {lemma or '-'}] {t}" for i, (t, lemma) in enumerate(zip(texts, lemmas))
    )
    prompt = (
        "Terjemahkan setiap definisi berikut ke Bahasa Indonesia. "
        "Balas HANYA dalam format JSON array of string, urutan harus sama "
        f"persis, tanpa teks lain di luar JSON.\n\n{numbered}"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None, help="Default: timpa file input")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None, help="Batasi jumlah entri yang diproses (untuk uji coba)")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES_PATH, help="Path ke file translation_rules.yaml")
    args = parser.parse_args()

    output = args.output or args.input

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set environment variable ANTHROPIC_API_KEY terlebih dahulu.")

    rules = load_rules(args.rules)
    system_prompt = build_system_prompt(rules)
    if rules:
        n_preserve = len(rules.get("preserve_terms") or [])
        n_forbidden = len(rules.get("forbidden_terms") or [])
        print(f"[INFO] Rules dimuat dari {args.rules}: {n_preserve} preserve_terms, {n_forbidden} forbidden_terms")

    client = anthropic.Anthropic()

    with args.input.open(encoding="utf-8") as f:
        data = json.load(f)

    pending_idx = [
        i for i, e in enumerate(data)
        if e.get("translation_status") == "pending" and e["definition"].get("en")
    ]
    if args.limit:
        pending_idx = pending_idx[: args.limit]

    print(f"Total entri pending: {len(pending_idx)}")

    for start in range(0, len(pending_idx), args.batch_size):
        batch_idx = pending_idx[start : start + args.batch_size]
        texts = [data[i]["definition"]["en"] for i in batch_idx]
        lemmas = [data[i].get("lemma", "") for i in batch_idx]

        try:
            translations = translate_batch(client, texts, lemmas, system_prompt)
        except Exception as e:
            print(f"[WARN] Batch gagal ({e}), skip batch ini.")
            continue

        if len(translations) != len(batch_idx):
            print("[WARN] Jumlah hasil tidak cocok, skip batch ini.")
            continue

        for i, translated in zip(batch_idx, translations):
            data[i]["definition"]["id"] = translated
            data[i]["translation_status"] = "machine"

        with output.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[OK] Batch {start}-{start+len(batch_idx)} selesai, tersimpan ke {output}")
        time.sleep(1)  # jeda sopan terhadap rate limit

    print("Selesai. Ingat: entri berstatus 'machine' perlu direview manusia sebelum dianggap 'reviewed'.")


if __name__ == "__main__":
    main()
