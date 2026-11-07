# Panduan Optimasi & Setup — Portal Orvelion (Jagoan Hosting + Cloudflare)

Dokumen ini melengkapi optimasi yang **sudah terpasang otomatis di kode** dengan
langkah-langkah **setup manual di sisi infrastruktur** (Cloudflare + cPanel Jagoan
Hosting) yang tidak bisa dilakukan lewat kode — tapi dampaknya besar untuk kecepatan
dan ketahanan saat event ramai.

---

## 1. Dua Lapis Optimasi

| Lapis | Status | Isi |
|---|---|---|
| **Kode (otomatis)** | ✅ Sudah terpasang | PJAX + transisi halus, gzip, ETag/304, micro-cache, cache-busting otomatis, agregasi SQL + index, rate limiting lembut, retry sync otomatis. Lihat `README.md` bagian *Optimasi Performa*. |
| **Infrastruktur (manual)** | 🔧 Perlu setup ±30–60 menit sekali | Cloudflare CDN/CDN cache, mode SSL, kompresi web server, restart app setelah deploy. Ikuti panduan di bawah. |

---

## 2. Kenapa Perlu Cloudflare (gratis)?

Tanpa Cloudflare, **semua** request — CSS, JS, gambar, HTML — menempuh perjalanan
ke server hosting di Indonesia/di mana pun server Jagoan berada. Saat event ramai:

1. **Bandwidth & koneksi hosting shared habis lebih cepat** (entry process penuh → error 508).
2. **Gambar & aset statis diunduh berulang** dari hosting oleh setiap pengunjung baru.
3. Tidak ada **perisai DDoS/spam** sebelum request sampai ke server.

Dengan Cloudflare (paket **Free** sudah cukup):

- Aset statis (JS/CSS/gambar) di-cache di **300+ kota di seluruh dunia** — pengunjung
  mengambil dari server terdekat, bukan dari hosting.
- **DDoS protection + WAF dasar** gratis menangkal banjir request sebelum menyentuh hosting.
- **HTTP/3 + Brotli + TLS 1.3** aktif otomatis — halaman lebih cepat dibuka.
- Waiting room & kuota **tetap akurat** karena HTML dinamis TIDAK di-cache Cloudflare
  (default-nya memang begitu, dan kita tidak mengubahnya).

---

## 3. Setup Cloudflare Step-by-Step

### Langkah A — Daftar & tambahkan domain

1. Daftar akun gratis di **cloudflare.com**.
2. Klik **Add a Site** → masukkan domain (mis. `osissmaigs.com`) → pilih paket **Free**.
3. Cloudflare memindai DNS existing → pastikan record yang muncul sesuai:
   - `A` record `@` → **IP server hosting** (cek di cPanel → General Information → Shared IP Address).
   - `CNAME` `www` → `osissmaigs.com.` (agar www ikut).
   - `MX` / `CNAME` email → biarkan **DNS only** (awan abu-abu), JANGAN di-proxy.
4. Cloudflare memberi **2 nameserver**, mis. `dana.ns.cloudflare.com` dan `rick.ns.cloudflare.com`.

### Langkah B — Ganti nameserver di Jagoan Hosting

1. Login ke **client area Jagoan Hosting** (member.jagoanhosting.com).
2. Menu **Domains → My Domains → Kelola Domain → Nameservers**.
3. Ganti NS lama (mis. `ns1.jagoanhosting.com`) menjadi 2 NS Cloudflare tadi.
4. Simpan. Propagasi biasanya 5 menit – 24 jam (rata-rata < 1 jam).
   Status bisa dipantau di dashboard Cloudflare → **Check nameservers now**.

> ⚠️ Selama propagasi jangan ada perubahan DNS lain. Situs tetap online via NS lama.

### Langkah C — Aktifkan proxy (awan oranye)

Di Cloudflare → **DNS → Records**:

| Record | Isi | Proxy |
|---|---|---|
| `A` @ | IP hosting | 🟠 **Proxied** (klik awan agar oranye) |
| `CNAME` www | domain utama | 🟠 **Proxied** |
| `MX`/email | — | ⚪ DNS only |

Awan oranye = traffic lewat CDN Cloudflare. Inilah yang mengaktifkan cache + proteksi.

### Langkah D — Setting SSL/TLS (PENTING — jangan sampai redirect loop)

Urutan harus begini:

1. **Dulu di cPanel**: pastikan SSL aktif untuk domain.
   cPanel → **SSL/TLS Status** → kalau statusnya belum ada sertifikat, klik
   **Run AutoSSL** (Let's Encrypt gratis dari Jagoan). Tunggu hingga domain
   terbuka `https://` langsung tanpa Cloudflare.
2. **Baru di Cloudflare**: **SSL/TLS → Overview → pilih mode `Full (Strict)`**.

> ❌ **Jangan pernah pakai mode `Flexible`** — bikin redirect loop & tidak aman
> (traffic Cloudflare→hosting tidak terenkripsi).
> Kalau muncul error 526 berarti sertifikat di hosting belum aktif — selesaikan
> Langkah D.1 dulu.

Lalu aktifkan di tab **SSL/TLS → Edge Certificates**:
- ✅ **Always Use HTTPS** — ON
- ✅ **Automatic HTTPS Rewrites** — ON
- **Minimum TLS Version** — 1.2

### Langkah E — Setting Speed & Caching

**SSL/TLS → Edge Certificates / Speed → Optimization:**

| Setting | Nilai | Alasan |
|---|---|---|
| Brotli | ✅ ON | Kompresi lebih efisien dari gzip |
| HTTP/3 (QUIC) | ✅ ON | Koneksi lebih cepat di jaringan mobile |
| Early Hints | ✅ ON | Browser mulai unduh aset sebelum HTML selesai |
| 0-RTT Connection Resumption | ✅ ON | Kunjungan berikutnya lebih cepat |
| **Rocket Loader** | ❌ **OFF** | ⚠️ Menunda eksekusi JS → **bisa merusak PJAX & urutan skrip**. Biarkan OFF! |

> ℹ️ Fitur *Auto Minify* Cloudflare sudah **dihentikan sejak 2024** — tidak perlu
> dicari. Kompresi sudah ditangani Brotli + gzip di aplikasi.

**Caching → Cache Rules → Create rule** (paket free dapat 5 rule):

*Rule 1 — aset statis berversi otomatis:*
```
Nama    : orvelion-static-js
Kondisi : URI Path starts with "/static/js/"
Setting : Eligible for cache
          Edge TTL: Respect origin cache control
```
(JS kita sudah otomatis berversi `?v=<mtime file>` — setiap deploy URL berubah
sendiri, jadi aman di-cache lama dan **tidak pernah basi**.)

*Rule 2 (opsional) — gambar (kalau ingin hemat bandwidth hosting lebih besar):*
```
Nama    : orvelion-static-images
Kondisi : URI Path starts with "/static/images/"
Setting : Eligible for cache
          Edge TTL: Ignore origin cache control, 1 hour
```
(Gambar jarang berubah. Konsekuensinya: jika banner diganti, perubahan terlihat
paling lama 1 jam — atau langsung dengan **Caching → Purge Everything**.)

> ❌ **JANGAN** pakai "Cache Everything" untuk seluruh situs — halaman kuota dan
> waiting room wajib selalu segar dari server.

---

## 4. Setting di cPanel Jagoan Hosting

1. **Optimize Website / Optimize** (cPanel → Software/Advanced):
   pilih **Compress all content** — mengaktifkan kompresi gzip di level web server
   (Apache/LiteSpeed) untuk aset statis yang dilayani langsung tanpa Cloudflare.
2. **Setup Python App** (cPanel → Software → Setup Python App):
   - Pastikan aplikasi menunjuk ke `passenger_wsgi.py` dan Python ≥ 3.9.
   - **Setiap selesai `git pull` / deploy: klik RESTART.** Tanpa restart, proses
     lama masih memakai kode lama (dan cache template/micro-cache lama).
3. **SSL**: sudah dibahas di Langkah D.1 (AutoSSL **sebelum** Full Strict).
   > Catatan: perpanjangan AutoSSL kadang gagal validasi kalau domain di-proxy
   > Cloudflare. Solusinya: jika notifikasi perpanjangan gagal, set sementara
   > record `A` jadi DNS only (awan abu-abu), jalankan **Run AutoSSL**, lalu
   > kembalikan ke Proxied.
4. **Backup sebelum hari-H**: cPanel → Backup → unduh **Full Account**
   (termasuk `nordelia.db` + `nordelia_registrations.json`).

---

## 5. Alur Deploy Baru (checklist singkat)

```
1. git pull            (di server / terminal cPanel)
2. Restart Python App  (cPanel → Setup Python App → RESTART)
3. Cloudflare → Caching → Purge Everything   (hanya jika mengubah CSS/gambar;
   JS tidak perlu — ?v= otomatis berubah sendiri)
```

---

## 6. Checklist Hari-H Event (traffic puncak)

- [ ] Cloudflare proxy aktif & mode **Full (Strict)** minimal H-1.
- [ ] Deploy final selesai + **Restart Python App** + **Purge Everything**.
- [ ] Pantau: Cloudflare → **Analytics** (traffic, cache HIT ratio, ancaman yang diblokir).
- [ ] Pantau: cPanel → **Resource Usage** (kalau entry process sering penuh,
      turunkan `MAX_ACTIVE_USERS` di `.env`, mis. dari 150 → 100 — waiting room
      yang mengatur sisanya).
- [ ] Darurat serangan: Cloudflare → Security → **Under Attack Mode** (pengunjung
      diminta verifikasi 5 detik, bot tersaring).
- [ ] Darurat data: semua pendaftaran tetap aman di `nordelia.db` lokal walau
      Google Sheet gangguan — thread retry otomatis mengirim ulang tiap 5 menit.

---

## 7. Variabel `.env` Baru (opsional, semua ada default aman)

| Variabel | Default | Fungsi |
|---|---|---|
| `REGISTER_RATE_LIMIT` | `150` | Batas POST `/api/nordelia/register` per IP per 5 menit. `0` = matikan. Naikkan jika satu lab sekolah mendaftar rame-rame dan menabrak batas. |
| `ORVELION_SYNC_RETRY` | `1` | `0` = matikan thread retry otomatis ke Google Sheet. |
| `MAX_ACTIVE_USERS` | `150` | Batas pengunjung bersamaan sebelum waiting room. |

---

## 8. Ide Optimasi Lanjutan (opsional, ada trade-off)

1. **Tailwind Play CDN → CSS hasil build** (dampak terbesar berikutnya).
   Saat ini `cdn.tailwindcss.com` adalah runtime JS ±100 KB yang membuat style
   di browser pada setiap kunjungan pertama. Menggantinya dengan file CSS statis
   hasil build (`npx tailwindcss`) memotong waktu muat pertama signifikan.
   **Trade-off**: hasil generate harus diaudit ulang setiap ada kelas baru, dan
   ada risiko beda tipis — makanya TIDAK dipasang otomatis demi jaminan
   "tampilan 100% tidak berubah".
2. **Rate limiting rule di Cloudflare** (free: 1 rule) — proteksi tambahan di edge,
   mis. batasi `rate(1m) > 60` untuk path `/api/nordelia/register` → Block/Challenge.
3. **Upgrade paket hosting / VPS kecil** — jika analytics menunjukkan ribuan
   pengunjung serentak, shared hosting akan jadi bottleneck utama terlepas dari
   semua optimasi ini. Waiting room sudah memitigasi, tapi kapasitas aslinya tetap
   terbatas paket.
4. **Monitoring eksternal gratis** (UptimeRobot / BetterStack) — ping ke `/`
   tiap 5 menit, dapat notifikasi kalau situs down.

---

## Cara memastikan PJAX benar-benar NYALA (verifikasi 1 menit)

Setelah deploy ke hosting, buka situs di browser lalu:

1. Tekan `F12` → tab **Console** → ketik: `window.OrvelionPJAX.swaps` → Enter.
2. Klik link ke halaman lain (mis. **Event**). Halaman berganti dengan transisi
   halus TANPA loading penuh (logo & header tidak berkedip).
3. Ketik lagi `window.OrvelionPJAX.swaps` → **angka bertambah = PJAX AKTIF.**

Kalau `window.OrvelionPJAX` undefined (pjax.js tidak termuat):

- Buka view-source (Ctrl+U): cari `static/js/pjax.js`.
  - **Tidak ada** → HTML lama masih ter-serve; deploy/pull di hosting belum
    berjalan, atau browser menyimpan cache lama → lakukan hard refresh
    (Ctrl+F5) sekali (HTML memang di-set `no-cache`, cukup sekali saja).
  - **Ada tapi request-nya 404** → file statis belum ikut ter-deploy; pastikan
    folder `static/js/pjax.js` ada di lokasi aplikasi hosting.

Catatan penting soal struktur di hosting: `passenger_wsgi.py` mendukung dua
layout (aplikasi di root, atau di dalam subfolder `web-orvelion-prod/`).
Yang penting: folder `static/` dan `templates/` harus berada SATU LEVEL dengan
folder `orvelion/` — jangan sampai kode ter-copy bersarang dua lapis.

## Hasil pengujian pra-delivery (7 Nov 2026, versi rebuild di atas repo tim)

- **11/11 tes transport lolos**: HTML identik dengan versi sebelumnya (beda
  hanya atribut tak terlihat: preconnect/lazy/decoding), gzip aktif (home
  31.930 B → 6.574 B, hemat 80%), ETag+304 bekerja, header cache benar
  (JS 7 hari berversi, CSS no-cache), POST pendaftaran sukses, header
  kapasitas antrean utuh, tanpa file sensitif.
- **19/19 tes browser end-to-end lolos** (headless browser sungguhan):
  navigasi PJAX tanpa reload penuh (penanda JS bertahan lintas navigasi),
  app.js ter-inisialisasi ulang pasca-swap, tombol kategori (11) dan chip
  jurusan OSN berfungsi, **modal pendaftaran terbuka setelah navigasi PJAX**,
  tombol back (popstate) benar, Tailwind tetap aktif, nol error console.
  Halaman sub kategori (OSN jurusan IPA=9 / IPS=4 tombol daftar) sesuai
  persis dengan yang dirender server.
- **Perbandingan visual**: screenshot home versi lama vs baru = 3 dari
  1.024.000 piksel berbeda (0,000%) — tampilan identik.
- Data uji pendaftaran dihapus kembali; `nordelia_registrations.json` dan
  database tidak berubah satu byte pun.

---

*Dokumen ini bagian dari repo `web-orvelion-prod`. Semua optimasi kode bersifat
non-fungsional: konten, tampilan, logika backend, dan struktur database tidak berubah.*
