#!/usr/bin/env python3
"""
parse_source.py

Mem-parsing file XML sumber Strong's menjadi JSON mentah sesuai
schema/strongs.schema.json (kolom `definition.id` masih null,
akan diisi oleh translate_id.py pada tahap berikutnya).

Struktur XML Hebrew dan Greek BERBEDA TOTAL (sudah diverifikasi langsung
terhadap file asli, bukan tebakan), sehingga masing-masing punya fungsi
parser sendiri:

  - Hebrew (openscriptures/HebrewLexicon -> HebrewStrong.xml):
      <entry id="H430">
        <w pos="n-m" pron="el-o-heem'" xlit="..." xml:lang="heb">אֱלֹהִים</w>
        <source>plural of <w src="H433">433</w>;</source>
        <meaning><def>gods</def> ... supreme <def>God</def> ...</meaning>
        <usage>angels, ... judges, ...</usage>
      </entry>
    Catatan: file ini pakai default XML namespace
    (http://openscriptures.github.com/morphhb/namespace).

  - Greek (openscriptures/strongs -> greek/StrongsGreekDictionaryXML_1.4/strongsgreek.xml):
      <entry strongs="00001">
        <strongs>1</strongs>
        <greek BETA="*A" unicode="Α" translit="A"/>
        <pronunciation strongs="al'-fah"/>
        <strongs_derivation>of Hebrew origin;</strongs_derivation>
        <strongs_def> the first letter of the alphabet; ... </strongs_def>
        <kjv_def>--Alpha.</kjv_def>
        <see language="GREEK" strongs="427"/>
      </entry>
    Catatan: file ini TIDAK pakai namespace. Nomor strongs perlu prefix
    "G" ditambahkan manual (dan leading zero dibuang).

Sumber data mentah (unduh manual ke folder raw/ sebelum menjalankan
script ini):
  - Hebrew: raw.githubusercontent.com/openscriptures/HebrewLexicon/master/HebrewStrong.xml
  - Greek : raw.githubusercontent.com/openscriptures/strongs/master/greek/StrongsGreekDictionaryXML_1.4/strongsgreek.xml

Penggunaan:
    python scripts/parse_source.py --lang hebrew --input raw/HebrewStrong.xml --output data/hebrew/strongs-hebrew.json
    python scripts/parse_source.py --lang greek  --input raw/strongsgreek.xml  --output data/greek/strongs-greek.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    sys.exit(
        "Dependensi 'lxml' belum terpasang. Jalankan: pip install lxml --break-system-packages"
    )

HEBREW_NS = {"h": "http://openscriptures.github.com/morphhb/namespace"}


def clean_text(value: str | None) -> str | None:
    """Rapikan whitespace berlebih dari teks hasil ekstraksi XML."""
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def element_text(el) -> str:
    """Ambil semua teks di dalam elemen (termasuk dari child seperti <def>),
    membuang tag anak tapi mempertahankan isi teksnya."""
    if el is None:
        return ""
    return clean_text("".join(el.itertext())) or ""


# ---------------------------------------------------------------------------
# Parser Hebrew
# ---------------------------------------------------------------------------

def parse_hebrew_entry(entry, source_id: str) -> dict | None:
    strong_number = entry.get("id")  # sudah berformat "H430"
    if not strong_number:
        return None

    w = entry.find("h:w", HEBREW_NS)
    if w is None:
        return None

    lemma = clean_text(w.text)
    translit = clean_text(w.get("xlit"))
    pron = clean_text(w.get("pron"))
    pos = clean_text(w.get("pos"))

    meaning_el = entry.find("h:meaning", HEBREW_NS)
    usage_el = entry.find("h:usage", HEBREW_NS)
    source_el = entry.find("h:source", HEBREW_NS)

    meaning_text = element_text(meaning_el)
    usage_text = element_text(usage_el)
    source_text = element_text(source_el)

    # Definisi EN: gabungkan source (etimologi singkat) + meaning.
    # usage disimpan terpisah ke kjv_translations (mirip kolom KJV Greek).
    definition_parts = [p for p in [source_text, meaning_text] if p]
    definition_en = " ".join(definition_parts) if definition_parts else usage_text

    kjv_list = [w.strip() for w in usage_text.split(",")] if usage_text else []

    # Nomor Strong turunan (dari <w src="H433">) yang muncul di <source>.
    derivatives_or_root = [
        el.get("src") for el in (source_el.findall("h:w", HEBREW_NS) if source_el is not None else [])
        if el.get("src")
    ]
    root = derivatives_or_root[0] if derivatives_or_root else None

    return {
        "strong_number": strong_number,
        "lemma": lemma or "",
        "transliteration": translit,
        "pronunciation": pron,
        "language": "hebrew",
        "part_of_speech": pos,
        "definition": {"en": definition_en or "", "id": None},
        "kjv_translations": kjv_list,
        "root": root,
        "derivatives": [],
        "occurrences_count": None,
        "source": source_id,
        "translation_status": "pending",
    }


def parse_hebrew_file(input_path: Path, source_id: str) -> list:
    tree = etree.parse(str(input_path))
    root = tree.getroot()
    entries = root.findall("h:entry", HEBREW_NS)
    results = [parse_hebrew_entry(e, source_id) for e in entries]
    return [r for r in results if r]


# ---------------------------------------------------------------------------
# Parser Greek
# ---------------------------------------------------------------------------

def parse_greek_entry(entry, source_id: str) -> dict | None:
    raw_number = entry.get("strongs")  # contoh: "00001"
    if not raw_number:
        return None
    strong_number = f"G{int(raw_number)}"  # buang leading zero, tambah prefix G

    greek_el = entry.find("greek")
    if greek_el is None:
        return None

    lemma = clean_text(greek_el.get("unicode"))
    translit = clean_text(greek_el.get("translit"))

    pron_el = entry.find("pronunciation")
    pron = clean_text(pron_el.get("strongs")) if pron_el is not None else None

    strongs_def_el = entry.find("strongs_def")
    kjv_def_el = entry.find("kjv_def")
    derivation_el = entry.find("strongs_derivation")

    definition_en = element_text(strongs_def_el)
    kjv_text = element_text(kjv_def_el)
    derivation_text = element_text(derivation_el)

    # kjv_def biasanya berformat ":--Alpha." atau ":--be much (sore) displeased, ..."
    kjv_clean = kjv_text.lstrip(":-").strip()
    kjv_list = [w.strip() for w in re.split(r",|;", kjv_clean) if w.strip()] if kjv_clean else []

    # Nomor Strong turunan dari <see language="GREEK" strongs="...">
    derivatives = [
        f"G{int(see.get('strongs'))}"
        for see in entry.findall("see")
        if see.get("language") == "GREEK" and see.get("strongs")
    ]

    return {
        "strong_number": strong_number,
        "lemma": lemma or "",
        "transliteration": translit,
        "pronunciation": pron,
        "language": "greek",
        "part_of_speech": None,  # tidak tersedia di sumber Greek ini
        "definition": {"en": definition_en or derivation_text or "", "id": None},
        "kjv_translations": kjv_list,
        "root": None,
        "derivatives": derivatives,
        "occurrences_count": None,
        "source": source_id,
        "translation_status": "pending",
    }


def parse_greek_file(input_path: Path, source_id: str) -> list:
    tree = etree.parse(str(input_path))
    root = tree.getroot()
    entries = root.findall(".//entry")
    results = [parse_greek_entry(e, source_id) for e in entries]
    return [r for r in results if r]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", required=True, choices=["hebrew", "greek"])
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-id", default=None, help="Nilai kolom 'source' (default otomatis)")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"File input tidak ditemukan: {args.input}")

    source_id = args.source_id or f"openscriptures-{args.lang}-strongs"

    if args.lang == "hebrew":
        results = parse_hebrew_file(args.input, source_id)
    else:
        results = parse_greek_file(args.input, source_id)

    if not results:
        sys.exit(
            "Tidak ada entri berhasil di-parse. Periksa apakah file input benar "
            "dan strukturnya belum berubah dari versi yang sudah diverifikasi."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[OK] {len(results)} entri '{args.lang}' ditulis ke {args.output}")


if __name__ == "__main__":
    main()
