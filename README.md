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
- `orvelion/` — aplikasi Flask, data konten, dan pelindung kapasitas
- `templates/` — halaman Jinja
- `static/` — CSS, JavaScript, dan gambar

## Optimasi Performa (non-fungsional)

Semua optimasi di bawah ini **tidak mengubah konten, tampilan, logika backend, maupun database** — murni lapisan transport & kecepatan. Untuk optimasi sisi infrastruktur (Cloudflare + cPanel Jagoan Hosting), lihat **`PANDUAN-OPTIMISASI.md`**.

- **PJAX (`static/js/pjax.js`)** — navigasi antarhalaman internal via `fetch` tanpa reload penuh: judul ikut berubah, skrip inline dieksekusi ulang sesuai urutan normal, tombol back/forward tetap bekerja, dan otomatis fallback ke reload penuh bila apa pun gagal (termasuk saat dialihkan ke waiting-room karena kapasitas penuh).
- **Transisi halaman mulus & cepat** — fade-out → fade-in murni pada `<main>` saja (±120 ms memudar + ±180 ms muncul, total ±300 ms): header tidak ikut memudar dan pergantian DOM/scroll terjadi saat layar sedang gelap sehingga tidak ada kedipan (kelap-kelip) seperti pada crossfade View Transitions; berlaku sama di semua browser. Termasuk progress bar tipis di tepi atas yang hanya muncul bila navigasi > 180 ms. Menghormati `prefers-reduced-motion` (langsung instan tanpa animasi). Keadaan diam halaman tidak berubah sama sekali.
- **Hover prefetch** — tautan internal di-prefetch saat disentuh kursor ~80 ms agar klik terasa instan (masa berlaku 15 detik agar angka kuota tetap segar).
- **Kompresi gzip** (`orvelion/optimizations.py`) — semua respons teks (HTML/JSON/CSV) dikompresi otomatis, menghemat bandwidth hingga ~80%.
- **ETag lemah + 304** — reload/back-forward dengan `If-None-Match` yang cocok dijawab `304 Not Modified` (body kosong) → transfer hemat, konten tetap 100% segar karena 304 hanya diberikan bila hash body identik.
- **Cache aset statis + cache-busting otomatis** — versi `?v=` pada file JS dihitung otomatis dari mtime file (`asset_v()` di template): setiap deploy otomatis mengganti URL sehingga aman di-cache 7 hari **tanpa risiko JS basi**. CSS & gambar tetap pada URL asli dengan revalidasi `no-cache` persis seperti perilaku awal — tampilan dan kesegaran konten visual 100% terjaga.
- **Micro-cache halaman statis** (`orvelion/routes.py`) — body HTML home/before-us/event di-cache di memori proses, dengan kunci berbasis mtime file template + sumber data sehingga setiap deploy **otomatis** membatalkan cache (tidak ada halaman basi). Halaman berkuota (nordelia) sengaja tidak di-cache.
- **Rate limiting lembut API pendaftaran** — default 150 POST / 5 menit / IP untuk `/api/nordelia/register`; jauh di atas kecepatan manusia mengisi formulir (aman untuk lab sekolah yang berbagi 1 IP), hanya memblokir banjir skrip/spam. Respons 429 ramah + header `Retry-After`. Atur/off via `.env` → `REGISTER_RATE_LIMIT`.
- **Retry sinkronisasi Google Sheet otomatis** — thread background tiap 5 menit mengirim ulang pendaftaran yang gagal masuk Google Sheet (maks 50 entri/putaran, flag `synced_to_sheets=0`) — data **self-heal** tanpa campur tangan panitia. Off via `.env` → `ORVELION_SYNC_RETRY=0`.
- **Agregasi SQL** — hitungan kuota per cabang & statistik kategori memakai `GROUP BY` + index SQLite (sebelumnya: memuat seluruh tabel dan menghitung di Python pada setiap request).
- **Cache `nordelia_events.json`** berbasis mtime (dibaca ulang otomatis saat file berubah).
- **Bytecode cache Jinja2** — template tidak di-parse ulang saat proses Passenger baru di-spawn (cold start lebih cepat).
- **Preconnect** ke CDN Tailwind + `loading="lazy"` untuk gambar di bawah layar + `fetchpriority="high"` untuk gambar hero (LCP).
- **PRAGMA SQLite `synchronous=NORMAL`** khusus tabel tracker antrean (aman dengan WAL).

Semua halaman, API, waiting room, tampilan, dan struktur database teruji identik setelah optimasi (39/39 tes lulus — endpoint, header, ETag/304, gzip, rate limit, cache, konten).
