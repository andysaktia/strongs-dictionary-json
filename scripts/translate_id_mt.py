#!/usr/bin/env python3
"""
translate_id_mt.py

Alternatif dari translate_id.py (yang diarsipkan -- lihat catatan di
bawah), memakai modul PyPI 'translate' (https://pypi.org/project/translate/)
sebagai provider terjemahan EN->ID. Default backend-nya adalah MyMemory API:
gratis, tanpa API key, tanpa perlu Ollama/model lokal terinstal.

PERBEDAAN PENTING dari translate_id.py:
    translate_id.py memakai LLM (Claude/Gemma) yang BISA diberi instruksi
    custom lewat system prompt (makanya translation_rules.yaml langsung
    "dipatuhi" oleh model). Modul 'translate' ini sebaliknya: mesin
    penerjemah literal/statistik (MyMemory), TIDAK punya konsep instruksi
    custom sama sekali -- dia hanya menerjemahkan teks apa adanya.

    Supaya translation_rules.yaml TETAP berlaku sebisa mungkin, script ini
    memakai 2 workaround:
    1. MASKING preserve_terms: sebelum dikirim ke MyMemory, istilah yang
       wajib dipertahankan (mis. "Elohim") disamarkan jadi placeholder
       supaya tidak ikut diterjemahkan/dirusak, lalu dikembalikan lagi
       setelah hasil terjemahan diterima.
    2. GUARD forbidden_terms: setelah hasil terjemahan diterima, script
       mencari kata terlarang (mis. "Allah") dan menggantinya dengan kata
       aman ("Tuhan" sebagai default), sambil MENANDAI entri tsb di log
       supaya direview manual -- karena penggantian otomatis begini tidak
       sehalus LLM yang paham konteks kalimat.

    Kedua workaround ini bukan jaminan sempurna seperti LLM (yang membaca
    konteks kalimat penuh), tapi jauh lebih baik daripada tidak ada
    penanganan sama sekali.

ARSIP translate_id.py:
    translate_id.py TIDAK dihapus/diubah -- disimpan sebagai arsip untuk
    dipakai lagi kalau suatu saat ada budget untuk model AI yang lebih
    baik (Claude API, atau model lokal yang lebih besar dari gemma3:4b).
    Kedua script independen, tidak saling import.

Instalasi:
    pip install translate --break-system-packages

Penggunaan:
    python scripts/translate_id_mt.py --input data/hebrew/strongs-hebrew.json --limit 20
    python scripts/translate_id_mt.py --input data/hebrew/strongs-hebrew.json --email nama@email.com

    --email: opsional, tapi SANGAT disarankan -- MyMemory kasih kuota 10x
    lebih besar (dari ~5.000 ke ~50.000 kata/hari) kalau pakai email asli
    dibanding kosong. Tidak perlu verifikasi apapun, cukup dicantumkan.

    pip install translate --break-system-packages

    Reset dulu entri lama yang hasilnya buruk dari percobaan sebelumnya
    python scripts/reset_status.py --input data/hebrew/strongs-hebrew.json --strong-numbers H1,H2,H3,H4,H5

    Uji coba kecil dulu
    python scripts/translate_id_mt.py --input data/hebrew/strongs-hebrew.json --limit 10 --email emailkamu@gmail.com
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit(
        "Dependensi 'pyyaml' belum terpasang. Jalankan: pip install pyyaml --break-system-packages"
    )

try:
    from translate import Translator
    from translate.exceptions import TranslationError
except ImportError:
    sys.exit(
        "Dependensi 'translate' belum terpasang. Jalankan: pip install translate --break-system-packages"
    )

DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "translation_rules.yaml"
DEFAULT_FORBIDDEN_REPLACEMENT = "Tuhan"
QUOTA_EXCEEDED_MARKERS = ["YOU USED ALL AVAILABLE", "MYMEMORY WARNING", "DAILY USAGE LIMIT"]


# ---------------------------------------------------------------------------
# Rules (translation_rules.yaml) -- salinan mandiri, TIDAK import dari
# translate_id.py, supaya script ini tetap jalan meski translate_id.py
# suatu saat diarsipkan/dipindah/dihapus.
# ---------------------------------------------------------------------------

def load_rules(rules_path: Path) -> dict:
    if not rules_path.exists():
        print(f"[WARN] File rules {rules_path} tidak ditemukan, lanjut tanpa aturan khusus.")
        return {}
    with rules_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Resolver deterministik untuk entri cross-reference kosong (bukan MT)
# Sama seperti di translate_id.py -- kasus ini murni struktural (mis.
# "(Aramaic) corresponding to 3"), MT literal JUGA berisiko salah
# menerjemahkannya jadi kalimat aneh, jadi tetap ditangani via template.
# ---------------------------------------------------------------------------

BARE_CROSS_REF_PATTERN = re.compile(r"^\(Aramaic\)\s+corresponding to\s+(\d+)\.?$", re.IGNORECASE)


def resolve_bare_cross_reference(definition_en: str, root: str | None) -> str | None:
    m = BARE_CROSS_REF_PATTERN.match(definition_en.strip())
    if not m:
        return None
    number = m.group(1)
    ref = root or f"H{number}"
    return f"(Aram) sesuai dengan {ref}"


def apply_deterministic_translations(data: list, pending_idx: list) -> list:
    remaining = []
    resolved_count = 0
    for i in pending_idx:
        entry = data[i]
        resolved = resolve_bare_cross_reference(entry["definition"]["en"], entry.get("root"))
        if resolved:
            entry["definition"]["id"] = resolved
            entry["translation_status"] = "machine"
            resolved_count += 1
        else:
            remaining.append(i)
    if resolved_count:
        print(f"[INFO] {resolved_count} entri cross-reference kosong diselesaikan via template "
              f"-- sisa {len(remaining)} entri lewat MT.")
    return remaining


# ---------------------------------------------------------------------------
# Masking preserve_terms & guard forbidden_terms
# ---------------------------------------------------------------------------

def mask_preserve_terms(text: str, preserve_terms: list) -> tuple[str, dict]:
    """Ganti istilah yang wajib dipertahankan dengan placeholder unik
    (mis. "Elohim" -> "ZZKEEP0ZZ") sebelum dikirim ke MT, supaya mesin
    penerjemah tidak ikut mengubah/merusaknya. MyMemory kadang tetap
    membiarkan kata asing apa adanya, tapi placeholder alfanumerik polos
    jauh lebih aman -- hampir pasti dilewati apa adanya oleh MT apapun."""
    mapping = {}
    masked = text
    for idx, item in enumerate(preserve_terms):
        term = item.get("term", "")
        if not term:
            continue
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        if pattern.search(masked):
            placeholder = f"ZZKEEP{idx}ZZ"
            masked = pattern.sub(placeholder, masked)
            mapping[placeholder] = term
    return masked, mapping


def unmask_preserve_terms(text: str, mapping: dict) -> str:
    for placeholder, term in mapping.items():
        # Placeholder alfanumerik kadang ikut "dirapikan" MT (mis. jadi
        # lowercase atau diberi spasi) -- cari case-insensitive supaya
        # tetap ketemu meski bentuknya sedikit berubah.
        pattern = re.compile(re.escape(placeholder), re.IGNORECASE)
        text = pattern.sub(term, text)
    return text


def apply_forbidden_term_guard(text: str, forbidden_terms: list) -> tuple[str, list]:
    """Cari kata terlarang di hasil terjemahan MT (mis. 'Allah' yang
    otomatis dipakai MyMemory untuk 'God'), ganti dengan kata aman, dan
    catat entri mana saja yang kena supaya bisa direview manual -- ini
    workaround statistik, BUKAN pemahaman konteks kalimat seperti LLM."""
    flagged = []
    result = text
    for item in forbidden_terms:
        term = item.get("term", "")
        if not term:
            continue
        replacement = item.get("replacement", DEFAULT_FORBIDDEN_REPLACEMENT)
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        if pattern.search(result):
            result = pattern.sub(replacement, result)
            flagged.append(term)
    return result, flagged


# ---------------------------------------------------------------------------
# Terjemahan per-item
# ---------------------------------------------------------------------------

def translate_single_mt(
    text: str, translator: "Translator", preserve_terms: list, forbidden_terms: list
) -> tuple[str, list]:
    masked, mapping = mask_preserve_terms(text, preserve_terms)
    raw = translator.translate(masked)
    unmasked = unmask_preserve_terms(raw, mapping)
    guarded, flagged = apply_forbidden_term_guard(unmasked, forbidden_terms)
    return guarded, flagged


def is_quota_exceeded(error: Exception) -> bool:
    message = str(error).upper()
    json_detail = ""
    if hasattr(error, "json"):
        json_detail = json.dumps(error.json).upper()
    combined = message + json_detail
    return any(marker in combined for marker in QUOTA_EXCEEDED_MARKERS)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None, help="Default: timpa file input")
    parser.add_argument("--limit", type=int, default=None, help="Batasi jumlah entri yang diproses (untuk uji coba)")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES_PATH)
    parser.add_argument("--from-lang", default="en")
    parser.add_argument("--to-lang", default="id")
    parser.add_argument("--email", default="", help="Opsional, tapi SANGAT disarankan -- naikkan kuota harian MyMemory 10x")
    parser.add_argument("--sleep", type=float, default=0.5, help="Jeda antar panggilan (detik), sopan terhadap API gratis")
    args = parser.parse_args()

    output = args.output or args.input

    rules = load_rules(args.rules)
    preserve_terms = rules.get("preserve_terms") or []
    forbidden_terms = rules.get("forbidden_terms") or []
    print(f"[INFO] Rules dimuat dari {args.rules}: {len(preserve_terms)} preserve_terms, "
          f"{len(forbidden_terms)} forbidden_terms")
    print("[INFO] Provider: MyMemory (via modul 'translate') -- MT literal, bukan LLM. "
          "preserve_terms dilindungi via masking, forbidden_terms via post-processing "
          "otomatis (hasil tetap perlu direview manual, sama seperti translation_status='machine').")

    if not args.email:
        print("[INFO] Tidak pakai --email -- kuota harian terbatas (~5.000 kata/hari). "
              "Tambahkan --email email@anda.com untuk kuota 10x lebih besar.")

    translator = Translator(from_lang=args.from_lang, to_lang=args.to_lang, email=args.email)

    with args.input.open(encoding="utf-8") as f:
        data = json.load(f)

    pending_idx = [
        i for i, e in enumerate(data)
        if e.get("translation_status") == "pending" and e["definition"].get("en")
    ]

    pending_idx = apply_deterministic_translations(data, pending_idx)
    with args.input.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if args.limit:
        pending_idx = pending_idx[: args.limit]

    print(f"Total entri pending untuk MT: {len(pending_idx)}")

    saved_count = 0
    flagged_count = 0
    for n, i in enumerate(pending_idx, start=1):
        entry = data[i]
        text = entry["definition"]["en"]

        try:
            translated, flagged = translate_single_mt(text, translator, preserve_terms, forbidden_terms)
        except TranslationError as e:
            if is_quota_exceeded(e):
                print(f"[STOP] Kuota harian MyMemory habis setelah {saved_count} entri tersimpan. "
                      f"Coba lagi besok, atau tambahkan --email untuk kuota lebih besar. Detail: {e}")
                break
            print(f"    [WARN] {entry['strong_number']}: gagal diterjemahkan ({e}), tetap 'pending'.")
            continue
        except Exception as e:
            print(f"    [WARN] {entry['strong_number']}: error tak terduga ({e}), tetap 'pending'.")
            continue

        if flagged:
            flagged_count += 1
            print(f"    [PERINGATAN FORBIDDEN-TERM] {entry['strong_number']}: kata terlarang "
                  f"{flagged} ditemukan & diganti otomatis -- WAJIB cek manual: \"{translated}\"")

        en_len = len(text)
        id_len = len(translated or "")
        if en_len > 0 and id_len / en_len < 0.25:
            print(f"    [PERINGATAN KUALITAS] {entry['strong_number']}: terjemahan jauh lebih pendek "
                  f"dari EN asli ({id_len} vs {en_len} karakter), cek manual: \"{translated}\"")

        entry["definition"]["id"] = translated
        entry["translation_status"] = "machine"
        saved_count += 1

        with output.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if n % 20 == 0 or n == len(pending_idx):
            print(f"[OK] {n}/{len(pending_idx)} diproses, {saved_count} tersimpan, "
                  f"{flagged_count} kena forbidden-term guard.")

        time.sleep(args.sleep)

    print(f"Selesai. {saved_count} entri tersimpan sebagai 'machine'. "
          f"{flagged_count} di antaranya kena forbidden-term guard -- WAJIB direview manual duluan. "
          "Semua entri 'machine' tetap perlu ditinjau manusia sebelum jadi 'reviewed'.")


if __name__ == "__main__":
    main()