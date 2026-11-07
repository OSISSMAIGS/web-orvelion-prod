"""
Optimasi non-fungsional untuk Portal OSIS Orvelion.

Semua optimasi di modul ini TIDAK mengubah konten, tampilan, logika backend,
maupun struktur database. Yang dioptimasi hanya lapisan transport & ketahanan:

1. Kompresi gzip untuk respons teks (HTML/JSON/CSV) — menghemat bandwidth
   hingga ~80% tanpa mengubah satu byte pun isi respons.
2. Kompresi + cache header untuk aset statis:
   - File JS berversi ?v= otomatis (mtime file, via asset_v di template)
     sehingga aman diberi cache panjang dan otomatis mem-bust tiap deploy.
   - File CSS/gambar tetap pada URL asli dan wajib revalidasi (no-cache),
     persis seperti perilaku situs sebelumnya — tampilan dan kesegaran
     konten visual 100% terjaga.
3. ETag lemah + respons 304 untuk HTML: browser yang me-reload / menekan
   back akan mengirim If-None-Match; jika isi halaman belum berubah,
   server menjawab 304 (body kosong) → transfer jauh lebih hemat.
4. Rate limiting LEMBUT untuk API pendaftaran (POST /api/nordelia/register):
   default 150 request / 5 menit / IP — jauh di atas kecepatan manusia
   mengisi formulir, hanya memblokir skrip spam/banjir saat event.
   Dimatikan dengan REGISTER_RATE_LIMIT=0 di .env.
5. Background retry sinkronisasi Google Sheet: pendaftaran yang gagal
   terkirim (jaringan gangguan) dicoba ulang otomatis tiap 5 menit
   (maks 50 entri per putaran) — data self-heal tanpa campur tangan.
   Dimatikan dengan ORVELION_SYNC_RETRY=0 di .env.
6. Header keamanan dasar (nosniff, referrer-policy).

Tidak ada dependensi baru — semuanya memakai pustaka standar Python,
aman dijalankan di shared hosting (Passenger/cPanel).
"""

import gzip
import hashlib
import os
import threading
import time
from collections import deque
from datetime import timedelta

from flask import Flask, Response, jsonify, request

# Tipe MIME yang layak dikompresi (semuanya teks)
_GZIP_MIMETYPES = {
    "text/html",
    "text/css",
    "text/plain",
    "text/csv",
    "text/javascript",
    "text/xml",
    "application/javascript",
    "application/x-javascript",
    "application/json",
    "application/xml",
    "image/svg+xml",
}

# MIME file JS — satu-satunya aset yang di-cache panjang karena
# URL-nya berversi ?v= eksplisit (pola bawaan template situs).
_JS_MIMETYPES = {
    "text/javascript",
    "application/javascript",
    "application/x-javascript",
}

_GZIP_MIN_SIZE = 512  # jangan kompres body kecil (tidak efisien)
_GZIP_LEVEL = 6       # keseimbangan kecepatan/rasio


# ======================================================================
# Rate limiting lembut untuk API pendaftaran (anti banjir saat event)
# ======================================================================

# 150 POST / 5 menit per IP. Seorang manusia butuh >= 30 detik mengisi
# formulir; 150/5mnt = 1 pendaftaran tiap 2 detik nonstop — hanya skrip
# yang bisa melampauinya. Lab sekolah yang berbagi 1 IP publik tetap aman.
try:
    REGISTER_RATE_LIMIT = int(os.environ.get("REGISTER_RATE_LIMIT", "150"))
except ValueError:
    REGISTER_RATE_LIMIT = 150
REGISTER_RATE_WINDOW = 300.0  # detik

_rate_hits: dict = {}
_rate_lock = threading.Lock()
_RATE_MAX_KEYS = 4096  # batas memori (IP unik yang dilacak)


def _client_ip() -> str:
    """IP klien terbaik yang tersedia.

    Prioritas CF-Connecting-IP (saat domain di-proxy Cloudflare — header
    ini di-set oleh Cloudflare), lalu hop terakhir X-Forwarded-For (proxy
    web server hosting), lalu remote_addr murni.
    """
    cip = (request.headers.get("CF-Connecting-IP") or "").strip()
    if cip:
        return cip
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[-1].strip()
    return (request.remote_addr or "unknown").strip() or "unknown"


def _register_rate_limit():
    """before_request: pembatas lembut khusus POST /api/nordelia/register."""
    if REGISTER_RATE_LIMIT <= 0:
        return None
    if request.method != "POST" or request.path != "/api/nordelia/register":
        return None

    ip = _client_ip()
    now = time.time()
    blocked_for = 0

    with _rate_lock:
        q = _rate_hits.get(ip)
        if q is None:
            q = _rate_hits[ip] = deque()
        # buang jejak yang lebih tua dari jendela
        while q and now - q[0] > REGISTER_RATE_WINDOW:
            q.popleft()
        if len(q) >= REGISTER_RATE_LIMIT:
            blocked_for = max(1, int(REGISTER_RATE_WINDOW - (now - q[0])) + 1)
        else:
            q.append(now)
        # jaga memori: sweep berkala key basi
        if len(_rate_hits) > _RATE_MAX_KEYS:
            cutoff = now - REGISTER_RATE_WINDOW
            for k in [k for k, v in _rate_hits.items() if not v or v[-1] < cutoff]:
                _rate_hits.pop(k, None)

    if blocked_for:
        resp = jsonify({
            "success": False,
            "error": (
                "Terlalu banyak percobaan pendaftaran dari jaringan/perangkat ini "
                f"dalam waktu singkat. Mohon tunggu sekitar {blocked_for} detik "
                "lalu coba lagi."
            ),
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(blocked_for)
        return resp
    return None


# ======================================================================
# Background retry sinkronisasi Google Sheet (data self-heal)
# ======================================================================

_sync_thread_started = False
_sync_thread_lock = threading.Lock()


def _start_sync_retry_thread() -> None:
    """Thread daemon: tiap 5 menit kirim ulang pendaftaran lokal yang belum
    berhasil masuk Google Sheet (maks 50 entri per putaran). Aman: hanya
    memanggil webhook untuk baris ber-flag synced_to_sheets=0, persis fungsi
    retry_unsynced() yang sudah ada (sebelumnya tidak pernah dipanggil)."""
    global _sync_thread_started

    if os.environ.get("ORVELION_SYNC_RETRY", "1").strip().lower() in ("0", "false", "off"):
        return

    with _sync_thread_lock:
        if _sync_thread_started:
            return
        _sync_thread_started = True

    def _worker():
        while True:
            time.sleep(300)  # jeda 5 menit; putaran pertama 5 menit setelah boot
            try:
                from orvelion.sheets_service import storage

                storage.retry_unsynced(limit=50)
            except Exception as e:
                print(f"[SYNC-RETRY] Putaran ulang gagal (dicoba lagi nanti): {e}")

    t = threading.Thread(target=_worker, name="orvelion-sync-retry", daemon=True)
    t.start()


# ======================================================================
# ETag lemah untuk HTML (+ respons 304)
# ======================================================================

def _etag_bare(body: bytes) -> str:
    """Nilai hash murni (tanpa kutip/W/) untuk perbandingan Werkzeug."""
    return hashlib.sha256(body).hexdigest()[:32]


def _weak_etag(bare: str) -> str:
    """Bentuk header: W/\"hash\" (perbandingan lemah, aman lintas encoding)."""
    return f'W/"{bare}"'


def _accepts_gzip() -> bool:
    return "gzip" in (request.headers.get("Accept-Encoding") or "").lower()


def _gzip_response(response):
    """Kompresi gzip transparan untuk respons teks yang cukup besar."""
    if response.direct_passthrough:
        # Respons streaming/file (mis. aset statis via send_file) — dilewati,
        # kompresi aset statis sebaiknya ditangani web server (Apache/LiteSpeed).
        return response
    if response.status_code < 200 or response.status_code in (204, 304):
        return response
    if "Content-Encoding" in response.headers:
        return response
    mimetype = (response.mimetype or "").lower()
    if mimetype not in _GZIP_MIMETYPES:
        return response
    if not _accepts_gzip():
        return response

    try:
        body = response.get_data()
    except Exception:
        return response
    if body is None or len(body) < _GZIP_MIN_SIZE:
        return response

    compressed = gzip.compress(body, compresslevel=_GZIP_LEVEL, mtime=0)
    if len(compressed) >= len(body):
        return response  # tidak ada penghematan, kirim apa adanya

    response.set_data(compressed)
    response.headers["Content-Encoding"] = "gzip"

    vary = response.headers.get("Vary")
    if vary:
        if "accept-encoding" not in vary.lower():
            response.headers["Vary"] = vary + ", Accept-Encoding"
    else:
        response.headers["Vary"] = "Accept-Encoding"
    return response


def init_optimizations(app: Flask) -> None:
    """Memasang seluruh optimasi non-fungsional ke aplikasi Flask."""

    # File JS berversi ?v= otomatis (mtime) → boleh di-cache panjang (7 hari).
    # CSS/gambar TIDAK berversi dan di-force no-cache di after_request
    # (lihat bawah) sehingga perilakunya sama persis dengan situs asli.
    if app.config.get("SEND_FILE_MAX_AGE_DEFAULT") is None:
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=7)

    # Rate limiting lembut API pendaftaran (before_request berjalan setelah
    # pelindung kapasitas antrean yang didaftarkan lebih dulu oleh init_queue).
    app.before_request(_register_rate_limit)

    # Background retry sinkronisasi Google Sheet (sekali per proses).
    _start_sync_retry_thread()

    # ------------------------------------------------------------------
    # after_request: ETag 304 + kompresi gzip + cache header + header
    # keamanan dasar. (after_request Flask berjalan urut terbalik
    #  pendaftaran; hook header kapasitas antrean tetap berjalan setelah
    #  ini dan tetap diterapkan pada respons 304.)
    # ------------------------------------------------------------------
    @app.after_request
    def apply_transport_optimizations(response):
        # --- ETag lemah untuk HTML (dihitung SEBELUM kompresi) ---
        # Reload / back-forward dengan If-None-Match yang cocok → 304,
        # body tidak perlu dikirim ulang. Konten tetap 100% segar karena
        # 304 hanya diberikan jika hash body saat ini sama persis.
        if (
            request.method in ("GET", "HEAD")
            and response.status_code == 200
            and (response.mimetype or "").lower() == "text/html"
            and not response.direct_passthrough
        ):
            try:
                body = response.get_data()
            except Exception:
                body = None
            if body:
                bare = _etag_bare(body)
                # If-None-Match memakai perbandingan LEMAH (RFC 9110 §13.1.2):
                # nilai di kedua set (kuat/lemah) dianggap cocok; Werkzeug
                # menyimpan nilai tanpa kutip & tanpa prefix W/.
                inm = request.if_none_match
                if inm.star_tag or inm.contains(bare) or inm.contains_weak(bare):
                    not_modified = Response(status=304)
                    not_modified.headers["ETag"] = _weak_etag(bare)
                    not_modified.headers["Cache-Control"] = "no-cache"
                    return not_modified
                response.headers["ETag"] = _weak_etag(bare)

        response = _gzip_response(response)

        # Halaman HTML bersifat dinamis (kuota berubah) → wajib selalu segar.
        # Browser tetap boleh menyimpan, tapi wajib revalidasi tiap kali.
        if (response.mimetype or "").lower() == "text/html" and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"

        # Aset statis non-JS (CSS/gambar): URL tidak berversi → wajib
        # revalidasi (persis perilaku asli situs) agar pembaruan file
        # langsung terlihat dan render browser identik sepenuhnya.
        if request.endpoint == "static":
            mt = (response.mimetype or "").lower()
            if mt not in _JS_MIMETYPES:
                response.headers["Cache-Control"] = "no-cache"

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response
