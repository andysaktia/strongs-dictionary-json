# Panduan Kontribusi

Terima kasih atas minat untuk berkontribusi ke `strongs-dictionary-json`!
Cara kontribusi yang paling berharga saat ini: **meninjau terjemahan Indonesia**
hasil AI (`translation_status: "machine"`) agar bisa naik status jadi
`"reviewed"`.

## Cara Berkontribusi

### 1. Meninjau / memperbaiki terjemahan

1. Fork repo ini.
2. Cari entri dengan `"translation_status": "machine"` di
   `data/hebrew/strongs-hebrew.json` atau `data/greek/strongs-greek.json`.
3. Perbaiki `definition.id` agar akurat dan idiomatik, lalu ubah
   `translation_status` menjadi `"reviewed"`.
4. Jalankan validasi lokal sebelum membuat PR:
   ```bash
   pip install -r requirements.txt
   python scripts/validate.py
   pytest tests/
   ```
5. Ajukan Pull Request. Jelaskan nomor Strong apa saja yang diubah.

### 2. Melaporkan kesalahan data

Buka [issue baru](../../issues/new) dengan menyertakan nomor Strong,
kesalahan yang ditemukan, dan (jika ada) referensi sumber yang benar.

### 3. Menambahkan fitur tooling

Untuk perubahan pada `scripts/`, `schema/`, atau workflow CI, mohon:
- Jelaskan motivasi perubahan di deskripsi PR.
- Pastikan `pytest tests/` tetap lolos.
- Jangan mengubah struktur schema (`schema/strongs.schema.json`) tanpa
  diskusi terlebih dahulu di issue, karena ini breaking change bagi
  pengguna dataset.

## Etika & Akurasi Teologis

Karena dataset ini menyangkut istilah teologis yang sensitif, mohon:
- Hindari opini/penafsiran teologis pribadi di kolom definisi — tetap pada
  makna leksikal/historis kata, sebagaimana sumber aslinya.
- Jika ragu dengan istilah tertentu, tinggalkan komentar di PR untuk
  didiskusikan alih-alih menebak.

## Kode Etik

Bersikap sopan dan konstruktif. Perbedaan pandangan denominasi/teologis
dapat muncul dalam diskusi terjemahan — fokus pada akurasi linguistik,
bukan perdebatan doktrinal.
