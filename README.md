# strongs-dictionary-json

> Strong's Hebrew & Greek Dictionary sebagai dataset JSON bersih, terstruktur,
> dan **dwibahasa (Indonesia + Inggris)** — dibangun untuk siapa pun yang
> mengembangkan tool, aplikasi, atau layanan Alkitab.

[![CI](https://github.com/andysaktia/strongs-dictionary-json/actions/workflows/ci.yml/badge.svg)](https://github.com/andysaktia/strongs-dictionary-json/actions/workflows/ci.yml)
[![npm version](https://img.shields.io/npm/v/strongs-dictionary-json.svg)](https://www.npmjs.com/package/strongs-dictionary-json)
[![License: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)
[![Data License: CC BY 4.0](https://img.shields.io/badge/data%20license-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATA)

---

## Kenapa Proyek Ini Ada

Strong's Dictionary adalah salah satu leksikon Ibrani & Yunani paling banyak
dipakai untuk studi Alkitab, tapi data terstrukturnya tersebar di berbagai
format lama (XML, DAT, format khusus aplikasi) dan **hampir tidak ada versi
JSON modern yang menyertakan terjemahan Bahasa Indonesia**. Proyek ini
mengisi celah itu: satu sumber data yang bersih, tervalidasi, dan siap pakai
untuk developer.

## Fitur

- **Format JSON modern**, tervalidasi otomatis lewat JSON Schema di setiap PR (CI).
- **Dwibahasa**: setiap entri punya `definition.en` dan `definition.id`.
- **Transparan soal kualitas terjemahan** lewat kolom `translation_status`
  (`pending` / `machine` / `reviewed` / `official-sabda`) — tidak ada klaim
  "resmi" untuk terjemahan yang belum ditinjau manusia.
- **Siap didistribusikan**: npm package, PyPI (rencana), dan akses langsung
  via CDN (jsDelivr) dari file statis di repo ini.
- **Contoh pemakaian** disediakan dalam JavaScript, Python, dan PHP.

## Struktur Data

```json
{
  "strong_number": "H430",
  "lemma": "אֱלֹהִים",
  "transliteration": "elohim",
  "pronunciation": "el-o-heem'",
  "language": "hebrew",
  "part_of_speech": "noun masculine plural",
  "definition": {
    "en": "gods, God, judges, angels",
    "id": "allah, Allah, para hakim, malaikat"
  },
  "kjv_translations": ["God", "god", "judge"],
  "root": "H433",
  "derivatives": ["H426"],
  "occurrences_count": 2606,
  "source": "openscriptures-hebrew-strongs",
  "translation_status": "machine"
}
```

Skema lengkap: [`schema/strongs.schema.json`](schema/strongs.schema.json).

## Struktur Repo

```
strongs-dictionary-json/
├── data/
│   ├── hebrew/strongs-hebrew.json      # Entri Ibrani (H1..)
│   ├── greek/strongs-greek.json        # Entri Yunani (G1..)
│   └── combined/strongs-full.json      # Gabungan, hasil build
├── schema/strongs.schema.json          # JSON Schema (draft-07)
├── scripts/
│   ├── parse_source.py                 # XML sumber -> JSON mentah
│   ├── translate_id.py                 # Batch translate EN -> ID via Claude API
│   ├── validate.py                     # Validasi schema
│   └── build_combined.py               # Gabungkan hebrew+greek, hitung statistik
├── examples/                           # Contoh pakai: js, python, php
├── tests/                              # pytest, dijalankan di CI
└── .github/workflows/                  # CI (validasi) + publish (npm)
```

## Instalasi & Pemakaian

### Via npm
```bash
npm install strongs-dictionary-json
```
```js
const dictionary = require("strongs-dictionary-json");
const elohim = dictionary.find(e => e.strong_number === "H430");
```

### Via file statis / CDN
```
https://cdn.jsdelivr.net/gh/andysaktia/strongs-dictionary-json@main/data/combined/strongs-full.json
```

### Via clone repo (untuk kontribusi / development pipeline)
```bash
git clone https://github.com/andysaktia/strongs-dictionary-json.git
cd strongs-dictionary-json
pip install -r requirements.txt
python scripts/validate.py
```

Lihat lebih banyak contoh di [`examples/`](examples/).

## Sumber Data

| Bahasa | Sumber mentah | Lisensi asal |
|---|---|---|
| Ibrani | [OpenScriptures Hebrew Lexicon](https://github.com/openscriptures/HebrewLexicon) (`HebrewStrong.xml`) | Public Domain (teks 1890) + CC BY 4.0 (struktur turunan) |
| Yunani | [OpenScriptures Strong's Dictionaries](https://github.com/openscriptures/strongs) (`greek/StrongsGreekDictionaryXML_1.4/strongsgreek.xml`) | Public Domain (teks 1890) + CC BY 4.0 (struktur turunan) |
| Terjemahan ID | AI-assisted (Claude, Anthropic) + tinjauan komunitas | CC BY-SA 4.0 |

Detail lengkap rantai lisensi & atribusi: [`LICENSE-DATA`](LICENSE-DATA).

## Alur Terjemahan (EN → ID)

1. `parse_source.py` mengekstrak entri dari XML sumber → `translation_status: "pending"`.
2. `translate_id.py` menerjemahkan secara batch via Claude API → status naik jadi `"machine"`.
3. Kontributor manusia meninjau & memperbaiki → status naik jadi `"reviewed"`.
4. (Rencana) Entri dari mitra resmi (mis. data SABDA YLSA) ditandai `"official-sabda"`.

Status ini **selalu terlihat di data**, supaya pengguna dataset tahu tingkat
kepercayaan tiap terjemahan sebelum dipakai di aplikasi mereka.

### Aturan Terjemahan Khusus (`scripts/translation_rules.yaml`)

`translate_id.py` membaca file [`scripts/translation_rules.yaml`](scripts/translation_rules.yaml)
setiap kali dijalankan dan menyuntikkan isinya ke system prompt Claude API.
Gunakan ini untuk mengontrol perilaku terjemahan tanpa mengubah kode:

- **`preserve_terms`** — nama/atribut Ibrani untuk Tuhan yang wajib
  dipertahankan sebagai transliterasi, tidak diterjemahkan (mis. `Elohim`,
  `YHWH`, `Adonai`, `El Shaddai`, `El Elyon`).
- **`forbidden_terms`** — kata yang tidak boleh muncul di hasil terjemahan
  (mis. `Allah` sebagai padanan nama diri Ibrani).
- **`general_guidelines`** — panduan tambahan bebas, mis. kapan boleh
  menerjemahkan wajar vs. kapan harus mempertahankan transliterasi.

Contoh menjalankan dengan file rules kustom (mis. untuk eksperimen tanpa
mengubah default):
```bash
python scripts/translate_id.py \
  --input data/hebrew/strongs-hebrew.json \
  --rules scripts/translation_rules.yaml \
  --limit 50
```

⚠️ Perubahan pada file rules **tidak otomatis berlaku surut** ke entri yang
sudah berstatus `"machine"` — hanya memengaruhi entri baru yang diterjemahkan
setelah perubahan. Untuk menerjemahkan ulang entri lama dengan rules baru,
ubah `translation_status` entri terkait kembali ke `"pending"` lalu jalankan
ulang script.

## Status Proyek

✅ **Fase 2 selesai — data mentah terisi.** 14.197 entri sudah berhasil di-parse
dari sumber asli (8.674 Hebrew + 5.523 Greek), semua lolos validasi schema.
Definisi `id` (Indonesia) masih `null` untuk semua entri — tahap berikutnya
adalah menjalankan `translate_id.py` secara bertahap. Lihat [Issues](../../issues)
untuk progres.

## Kontribusi

Kontribusi sangat terbuka, terutama untuk **meninjau terjemahan Indonesia**.
Baca [`CONTRIBUTING.md`](CONTRIBUTING.md) untuk panduan lengkap.

## Lisensi

- Kode & tooling: [MIT](LICENSE)
- Dataset: lihat rincian lengkap di [`LICENSE-DATA`](LICENSE-DATA)

## Ucapan Terima Kasih

Dibangun di atas kerja keras [OpenScriptures](https://github.com/openscriptures)
dalam mendigitalkan leksikon Ibrani & Yunani, dan James Strong atas karya
aslinya (1890). Proyek ini juga terinspirasi oleh misi
[SABDA YLSA](https://www.sabda.org) dalam menyediakan sumber daya Alkitab
digital untuk gereja-gereja di Indonesia.
