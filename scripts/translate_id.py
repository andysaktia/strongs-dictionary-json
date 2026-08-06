#!/usr/bin/env python3
"""
translate_id.py

Mengisi kolom definition.id secara batch, lalu menandai
translation_status="machine". Entri yang sudah berstatus "reviewed"
atau "official-sabda" TIDAK akan ditimpa.

Mendukung DUA provider terjemahan:

  1. claude (default) -- via Anthropic API. Butuh ANTHROPIC_API_KEY.
     Estimasi biaya untuk seluruh dataset (~14.000 entri): sekitar $3-5.

  2. ollama -- via model lokal (mis. Gemma) lewat Ollama, 100% gratis,
     jalan di komputer sendiri, tidak butuh API key maupun internet
     (setelah model diunduh). Butuh Ollama sudah jalan di localhost.
     Kualitas & konsistensi terjemahan bergantung pada ukuran model
     yang dipakai -- model kecil (mis. gemma3:4b) cocok untuk RAM
     terbatas (<=8GB), tapi hasilnya perlu lebih banyak review manual
     dibanding Claude untuk definisi yang bernuansa.

Kedua provider SAMA-SAMA membaca scripts/translation_rules.yaml dan
menyuntikkannya ke system prompt, jadi aturan preserve/forbidden terms
(mis. pertahankan "Elohim"/"YHWH", larang "Allah") tetap berlaku di
provider manapun -- ini yang membedakan dari modul translate biasa
(Google Translate/Argos) yang tidak bisa menerima instruksi custom.

Penggunaan:
    # Provider Claude (default)
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/translate_id.py --input data/hebrew/strongs-hebrew.json --limit 50

    # Provider Ollama (gratis, lokal)
    ollama pull gemma3:4b   # sekali saja
    python scripts/translate_id.py --input data/hebrew/strongs-hebrew.json \
        --provider ollama --ollama-model gemma3:4b --limit 50

Catatan desain (lihat README > "Alur Terjemahan"):
    - Berjalan secara batch kecil (default 20 entri/panggilan) supaya
      mudah diaudit dan dihentikan/diulang tanpa kehilangan progres.
    - Selalu tulis ulang file output setelah setiap batch (resume-safe).

    python scripts/translate_id.py --input data/hebrew/strongs-hebrew.json --provider ollama --ollama-model gemma3:4b --limit 5
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit(
        "Dependensi 'pyyaml' belum terpasang. Jalankan: pip install pyyaml --break-system-packages"
    )

CLAUDE_MODEL = "claude-sonnet-5"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

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


def build_user_prompt(texts: list[str], lemmas: list[str]) -> str:
    # Sertakan lemma (kata asli) di samping definisi EN, supaya model tahu
    # persis kata apa yang sedang diterjemahkan -- penting untuk mengecek
    # apakah entri ini termasuk nama/atribut Tuhan yang wajib dipertahankan.
    numbered = "\n".join(
        f"{i+1}. [lemma: {lemma or '-'}] {t}" for i, (t, lemma) in enumerate(zip(texts, lemmas))
    )
    return (
        "Terjemahkan setiap definisi berikut ke Bahasa Indonesia. "
        "Balas HANYA dalam format JSON array of string, urutan harus sama "
        f"persis, tanpa teks lain di luar JSON.\n\n{numbered}"
    )


def extract_json_array(raw: str) -> list:
    """Bersihkan output model (hapus code fence, teks pembuka/penutup di
    luar JSON) lalu parse jadi list. Model lokal (Ollama) sering kurang
    disiplin ikut instruksi 'HANYA JSON' dibanding Claude, jadi ekstraksi
    di sini lebih toleran: cari substring [...] pertama kalau parse
    langsung gagal."""
    raw = raw.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


# ---------------------------------------------------------------------------
# Provider: Claude API
# ---------------------------------------------------------------------------

def translate_batch_claude(client, texts: list[str], lemmas: list[str], system_prompt: str) -> list[str]:
    prompt = build_user_prompt(texts, lemmas)
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    return extract_json_array(raw)


def make_claude_client():
    try:
        import anthropic
    except ImportError:
        sys.exit(
            "Dependensi 'anthropic' belum terpasang. Jalankan: pip install anthropic --break-system-packages"
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set environment variable ANTHROPIC_API_KEY terlebih dahulu.")
    return anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Provider: Ollama (lokal, gratis)
# ---------------------------------------------------------------------------

def translate_batch_ollama(
    texts: list[str], lemmas: list[str], system_prompt: str, model: str, host: str
) -> list[str]:
    import urllib.request
    import urllib.error

    prompt = build_user_prompt(texts, lemmas)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        # format="json" membantu model lokal lebih disiplin balas JSON,
        # meski tidak sekuat instruksi eksplisit pada model besar.
        "format": "json",
        "options": {"temperature": 0.2},
    }
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Tidak bisa menghubungi Ollama di {host}. Pastikan Ollama sudah jalan "
            f"('ollama serve' atau aplikasi Ollama terbuka) dan model '{model}' sudah "
            f"di-pull ('ollama pull {model}'). Detail: {e}"
        )

    raw = body.get("message", {}).get("content", "")
    if not raw:
        raise RuntimeError(f"Respons Ollama kosong/tidak terduga: {body}")
    return extract_json_array(raw)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None, help="Default: timpa file input")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None, help="Batasi jumlah entri yang diproses (untuk uji coba)")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES_PATH, help="Path ke file translation_rules.yaml")
    parser.add_argument("--provider", choices=["claude", "ollama"], default="claude")
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL, help="Nama model Ollama, mis. gemma3:4b")
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    args = parser.parse_args()

    output = args.output or args.input

    rules = load_rules(args.rules)
    system_prompt = build_system_prompt(rules)
    if rules:
        n_preserve = len(rules.get("preserve_terms") or [])
        n_forbidden = len(rules.get("forbidden_terms") or [])
        print(f"[INFO] Rules dimuat dari {args.rules}: {n_preserve} preserve_terms, {n_forbidden} forbidden_terms")

    claude_client = None
    if args.provider == "claude":
        claude_client = make_claude_client()
    else:
        print(f"[INFO] Provider: ollama, model: {args.ollama_model}, host: {args.ollama_host}")
        print("[INFO] Kualitas hasil model lokal biasanya lebih bervariasi daripada Claude -- "
              "cek beberapa hasil pertama secara manual sebelum lanjut batch besar.")

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
            if args.provider == "claude":
                translations = translate_batch_claude(claude_client, texts, lemmas, system_prompt)
            else:
                translations = translate_batch_ollama(
                    texts, lemmas, system_prompt, args.ollama_model, args.ollama_host
                )
        except Exception as e:
            print(f"[WARN] Batch gagal ({e}), skip batch ini.")
            continue

        if len(translations) != len(batch_idx):
            print(f"[WARN] Jumlah hasil tidak cocok ({len(translations)} vs {len(batch_idx)}), skip batch ini.")
            continue

        for i, translated in zip(batch_idx, translations):
            data[i]["definition"]["id"] = translated
            data[i]["translation_status"] = "machine"

        with output.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[OK] Batch {start}-{start+len(batch_idx)} selesai, tersimpan ke {output}")
        time.sleep(1 if args.provider == "claude" else 0)  # jeda sopan hanya untuk API berbayar

    print("Selesai. Ingat: entri berstatus 'machine' perlu direview manusia sebelum dianggap 'reviewed'.")


if __name__ == "__main__":
    main()