# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
dan proyek ini mengikuti [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Struktur repo awal: schema, scripts ETL (`parse_source.py`,
  `translate_id.py`, `validate.py`, `build_combined.py`), CI (validasi +
  publish npm), unit test dasar.
- Dokumentasi: README, CONTRIBUTING, LICENSE, LICENSE-DATA.
- Contoh pemakaian dataset (JavaScript, Python, PHP).
- `scripts/translation_rules.yaml` — aturan penerjemahan (istilah wajib
  dipertahankan seperti Elohim/YHWH/Adonai, istilah terlarang seperti
  "Allah" untuk nama diri Ibrani), disuntikkan otomatis ke system prompt
  `translate_id.py`.
- **Data mentah Fase 2**: 14.197 entri berhasil di-parse dari sumber XML asli
  (8.674 Hebrew + 5.523 Greek), semua lolos validasi schema. Kolom
  `definition.id` masih kosong, menunggu proses `translate_id.py`.

### Notes
- Terjemahan Indonesia (`translation_status`) masih 100% `"pending"` —
  belum ada entri yang diterjemahkan.
- **Halaman demo pencarian** (`docs/index.html`) — statis, tema manuskrip,
  fetch data dari jsDelivr CDN, siap dipublikasikan via GitHub Pages.
  Pencarian toleran diakritik (mis. "agape" tetap menemukan "agápē").