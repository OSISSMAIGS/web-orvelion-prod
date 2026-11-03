# Portal OSIS Orvélion (Flask)

Situs resmi Kabinet Orvélion, OSIS SMA Ignatius Global School 2026–2027.

## Menjalankan lokal

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Buka [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Struktur

- `app.py` — titik masuk
- `orvelion/` — aplikasi Flask, data konten, pelindung kapasitas, dan modul pendaftaran (`nordelia.py`)
- `templates/` — halaman Jinja
- `static/` — CSS, JavaScript, dan gambar

## Pendaftaran Lomba Nordelia (halaman `/daftar`)

Formulir di halaman `/daftar` meneruskan pendaftaran ke spreadsheet rekap
panitia lewat webhook Google Apps Script.

Pintu masuknya ada di **kartu & modal detail event** (halaman Event) — bukan di
navbar, karena pendaftaran terikat event tertentu, bukan fitur situs se-level
menu. Tombol "Daftar" hanya muncul di event yang memiliki field `daftar_url`
di `orvelion/content.py` (saat ini: **Nordelia 2026**, festival lomba 41 cabang).
Begitu event lain resmi membuka pendaftaran, tinggal tambahkan
`"daftar_url": "/daftar"` pada entri event tersebut.

Supaya aktif:

1. Salin `.env.example` jadi `.env` di akar repo.
2. Isi `GOOGLE_SHEET_WEBHOOK_URL` dengan URL deployment Apps Script panitia
   (yang diakhiri `/exec`).
3. Jalankan ulang `python app.py`.

Tanpa `.env`, halaman tetap terbuka tapi menampilkan pemberitahuan bahwa
pendaftaran online belum aktif — tidak ada yang crash.

Kenapa dikirim lewat server Flask, bukan langsung dari browser? Supaya URL
webhook tidak tersebar di kode halaman (bisa dipakai spam) dan semua input
tervalidasi dulu: nama, format kelas (cth. `10.1 CGC`), nomor WhatsApp
(dinormalkan ke format `08…`), dan cabang lomba harus ada di daftar resmi.
Ada juga rem per-IP: maksimal 5 kiriman per 10 menit dari perangkat yang sama.

Daftar lomba & cabangnya dikelola di `orvelion/nordelia.py`
(`KATEGORI_LOMBA`) — kalau panitia menambah cabang baru, edit di situ lalu
build ulang CSS bila ikut menyentuh kelas Tailwind.

## Optimasi performa (baca ini sebelum edit CSS/kelas)

1. **Tailwind sudah di-build statis** ke `static/css/tailwind.css` — situs tidak
   lagi memakai Play CDN (dulu ~400 KB JS + kompilator CSS jalan di browser
   tiap pengunjung). Setelah menambah/mengubah kelas Tailwind di `templates/`
   atau `static/js/`, **wajib jalankan lalu commit hasilnya**:

   ```bash
   tools/build-css.sh    # butuh bun (bunx) atau node (npx)
   ```

2. **Navigasi antarhalaman tanpa reload penuh** (soft navigation, PJAX) sudah
   aktif di `static/js/app.js`. HTML saja yang ditukar — CSS/JS/gambar tidak
   diunduh ulang. Matikan per-link tertentu dengan menambah `data-soft="off"`.

3. **Cache cerdas**: CSS/JS memakai versi `?v=` otomatis (mtime) + header
   `immutable` setahun; HTML `no-cache` agar limiter kapasitas selalu sahih.
   Tidak perlu mengatur apa pun manual.
