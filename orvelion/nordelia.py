"""Pendaftaran lomba Nordelia 2026 — jembatan situs -> Google Spreadsheet.

Alur: form di /daftar -> validasi di server (sini) -> diteruskan ke webhook
Google Apps Script milik panitia -> masuk sheet "Master Pendaftaran" + sheet
per cabang lomba.

Kenapa lewat server, bukan langsung dari browser?
1. URL webhook tidak bocor ke kode halaman (bisa disalahgunakan buat spam).
2. Input tervalidasi dulu (nama, kelas, nomor WhatsApp, cabang harus sah) —
   webhook Apps Script-nya sendiri menerima payload apa pun.
3. Ada rem pengiriman per-IP supaya satu orang tidak bisa banjir-baris.

Konfigurasi: salin .env.example jadi .env lalu isi GOOGLE_SHEET_WEBHOOK_URL.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any

# --------------------------------------------------------------------------
# Daftar lomba — satu sumber kebenaran untuk form & validasi.
# Selaras dengan sheet "Format Pendaftaran" spreadsheet Nordelia (1 lomba 1 sheet).
# ---------------------------------------------------------------------------

KATEGORI_LOMBA = [
    {
        "id": "akademik",
        "nama": "Akademik",
        "lomba": [
            {"id": "literasi-numerasi", "nama": "Literasi Numerasi"},
            {"id": "literasi-bahasa-indonesia", "nama": "Literasi Bahasa Indonesia"},
            {"id": "literasi-science", "nama": "Literasi Science"},
            {
                "id": "olimpiade-sains",
                "nama": "Olimpiade Sains (9 Cabang)",
                "sub_label": "Cabang Olimpiade",
                "subs": ["Matematika", "Fisika", "Kimia", "Biologi", "Astronomi", "Geografi", "Informatika", "Ekonomi", "Kebumian"],
                "cabang_fmt": "Olimpiade {}",
            },
            {"id": "olimpiade-ai", "nama": "Olimpiade Kecerdasan Artifisial (AI)"},
        ],
    },
    {
        "id": "debat",
        "nama": "Debat",
        "lomba": [
            {
                "id": "lomba-debat-indonesia",
                "nama": "Lomba Debat Indonesia",
                "sub_label": "Jenis Debat",
                "subs": ["LDBI", "NSDC"],
                "cabang_fmt": "Lomba Debat Indonesia",
                "extra_field": "jenis_debat",
            },
        ],
    },
    {
        "id": "bahasa asing",
        "nama": "Bahasa Asing",
        "lomba": [
            {
                "id": "lomba-bahasa-asing",
                "nama": "Lomba Bahasa Asing",
                "sub_label": "Cabang Bahasa",
                "subs": [
                    "Bahasa Jerman", "Bahasa Jepang", "Bahasa Korea", "Bahasa Mandarin",
                    "Bahasa Spanyol", "Bahasa Prancis", "Bahasa Arab", "Kaligrafi",
                    "Menyanyi Mandarin", "Cosplay", "Story Telling",
                ],
            },
        ],
    },
    {
        "id": "fls3n",
        "nama": "FLS3N (Seni)",
        "lomba": [
            {
                "id": "fls3n",
                "nama": "FLS3N",
                "sub_label": "Cabang FLS3N",
                "subs": ["Baca Puisi", "Cipta Puisi", "Cerita Pendek", "Monolog", "Poster", "Gitar", "Menyanyi", "Kriya", "Komik", "Tari"],
                "cabang_fmt": "FLS3N {}",
            },
        ],
    },
    {
        "id": "o2sn",
        "nama": "O2SN (Olahraga)",
        "lomba": [
            {
                "id": "o2sn",
                "nama": "O2SN",
                "sub_label": "Cabang O2SN",
                "subs": ["Silat", "Atletik", "Basket", "Futsal", "Voli", "Catur"],
                "cabang_fmt": "O2SN {}",
            },
        ],
    },
]

# Saran isian kelas (tetap bebas diketik manual — ini cuma bantuan).
KELAS_CONTOH = [
    "10.1 CGC", "10.2 MAYOR", "10.3 MAYOR",
    "11.1 CGC", "11.2 CGC", "11.1 MAYOR", "11.2 MAYOR",
    "12.1 CGC", "12.2 MAYOR",
]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _indeks_cabang() -> dict[str, dict[str, Any]]:
    """cabang_id -> {kategori, lomba, sub, cabang_name, extra}."""
    indeks: dict[str, dict[str, Any]] = {}
    for kat in KATEGORI_LOMBA:
        for lomba in kat["lomba"]:
            subs = lomba.get("subs")
            if not subs:
                nama = lomba["nama"]
                indeks[_slug(nama)] = {
                    "kategori": kat, "lomba": lomba, "sub": None, "cabang_name": nama,
                }
                continue
            fmt = lomba.get("cabang_fmt", "{}")
            for sub in subs:
                cabang_name = fmt.format(sub) if "{}" in fmt else fmt
                indeks[_slug(cabang_name)] = {
                    "kategori": kat, "lomba": lomba, "sub": sub, "cabang_name": cabang_name,
                }
    return indeks


CABANG_INDEKS = _indeks_cabang()


# --------------------------------------------------------------------------
# Membaca konfigurasi (.env di akar repo, tanpa dependensi tambahan).
# ---------------------------------------------------------------------------

def _muat_dotenv() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            for baris in fh:
                baris = baris.strip()
                if not baris or baris.startswith("#") or "=" not in baris:
                    continue
                kunci, _, nilai = baris.partition("=")
                kunci, nilai = kunci.strip(), nilai.strip().strip('"').strip("'")
                if kunci and kunci not in os.environ:
                    os.environ[kunci] = nilai
    except OSError:
        pass  # tidak ada .env -> pakai os.environ apa adanya


_muat_dotenv()


def webhook_url() -> str:
    return os.environ.get("GOOGLE_SHEET_WEBHOOK_URL", "").strip()


def webhook_aktif() -> bool:
    return webhook_url().startswith("https://")


# --------------------------------------------------------------------------
# Validasi input — semua pesan balik dalam Bahasa Indonesia, siap tampil.
# ---------------------------------------------------------------------------

_RX_NAMA = re.compile(r"^[^\W\d_](?:[^\W\d_.'\- ]*[ .'\-]?)*$", re.UNICODE)
_RX_KELAS = re.compile(r"^1[0-2]\s*[.,:\-]?\s*\S+(?:\s\S+){0,2}$")


def _normalisasi_wa(no: str) -> str | None:
    no = re.sub(r"[\s\-\.\(\)]", "", no)
    if no.startswith("+"):
        no = no[1:]
    if no.startswith("62"):
        no = "0" + no[2:]
    if re.fullmatch(r"08\d{7,12}", no):
        return no
    return None


def validasi(data: dict[str, Any]) -> dict[str, str]:
    """Kembalikan {field: pesan_error} — kosong berarti lolos."""
    galat: dict[str, str] = {}

    nama = str(data.get("nama_lengkap") or "").strip()
    if not (3 <= len(nama) <= 60):
        galat["nama_lengkap"] = "Nama lengkap 3-60 karakter ya."
    elif not _RX_NAMA.match(nama) or not re.search(r"[^\W\d_]", nama.replace(" ", "")):
        galat["nama_lengkap"] = "Isi nama dengan huruf (boleh disertai titik atau tanda petik)."

    kelas = str(data.get("kelas") or "").strip()
    if not (3 <= len(kelas) <= 24):
        galat["kelas"] = "Kelas belum diisi (contoh: 10.1 CGC)."
    elif not _RX_KELAS.match(kelas):
        galat["kelas"] = "Format kelas seperti 10.1 CGC / 11.2 MAYOR (mulai 10, 11, atau 12)."

    wa = _normalisasi_wa(str(data.get("whatsapp") or ""))
    if not wa:
        galat["whatsapp"] = "Nomor WhatsApp belum benar (contoh: 081234567890)."

    cabang_id = str(data.get("cabang_id") or "")
    info = CABANG_INDEKS.get(cabang_id)
    if not info:
        galat["cabang_id"] = "Pilih kategori dan cabang lombanya dulu."
    else:
        subs = info["lomba"].get("subs")
        sub = str(data.get("sub") or "")
        if subs and sub not in subs:
            galat["cabang_id"] = "Pilih cabang lombanya dulu."

    return galat


def susun_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    """Rakit payload final buat webhook — hanya field yang sah."""
    info = CABANG_INDEKS.get(str(data.get("cabang_id") or ""))
    if not info:
        return None
    payload: dict[str, Any] = {
        "category_id": info["kategori"]["id"],
        "cabang_id": str(data["cabang_id"]),
        "cabang_name": info["cabang_name"],
        "nama_lengkap": str(data["nama_lengkap"]).strip(),
        "kelas": str(data["kelas"]).strip(),
        "whatsapp": _normalisasi_wa(str(data["whatsapp"])) or "",
    }
    extra = info["lomba"].get("extra_field")
    if extra:
        # Lomba dengan pilihan sub (mis. jenis debat LDBI/NSDC): sub dipilih
        # pengguna, bukan hasil tebakan — ambil dari data yang tervalidasi.
        sub = str(data.get("sub") or "")
        if sub in info["lomba"].get("subs", []):
            payload[extra] = sub
    return payload


# --------------------------------------------------------------------------
# Rem pengiriman per-IP (sederhana, cukup untuk satu proses Flask).
# ---------------------------------------------------------------------------

_RATE_LOCK = threading.Lock()
_RATE_LOG: dict[str, list[float]] = {}
_RATE_JENDELA = 600      # 10 menit
_RATE_MAKS = 5           # maksimal 5 pendaftaran per IP per jendela


def _ip_pengirim() -> str:
    # Dipanggil dari routes; fallback "lokal" kalau konteks request tiada.
    try:
        from flask import request

        return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or request.remote_addr or "lokal")
    except RuntimeError:
        return "lokal"


def boleh_kirim() -> bool:
    ip = _ip_pengirim()
    kini = time.time()
    with _RATE_LOCK:
        riwayat = [t for t in _RATE_LOG.get(ip, []) if kini - t < _RATE_JENDELA]
        _RATE_LOG[ip] = riwayat
        if len(riwayat) >= _RATE_MAKS:
            return False
        riwayat.append(kini)
        # Bersih-bersih IP lama supaya memori tidak merambat.
        if len(_RATE_LOG) > 4096:
            for kunci, tanda in list(_RATE_LOG.items()):
                if not tanda or kini - tanda[-1] > _RATE_JENDELA:
                    _RATE_LOG.pop(kunci, None)
        return True


# --------------------------------------------------------------------------
# Pengiriman ke Apps Script.
# Apps Script membalas 302 -> URL echo; respons JSON-nya dibaca dari sana.
# --------------------------------------------------------------------------

class _TanpaRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def kirim_ke_webhook(payload: dict[str, Any]) -> tuple[bool, str]:
    url = webhook_url()
    if not webhook_aktif():
        return False, "Pendaftaran online belum dikonfigurasi panitia (GOOGLE_SHEET_WEBHOOK_URL kosong)."

    opener = urllib.request.build_opener(_TanpaRedirect())
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            dengan = opener.open(req, timeout=20)
            body = dengan.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            if err.code not in (301, 302, 303, 307, 308) or not err.headers.get("Location"):
                raise
            # Ikuti URL echo dengan GET (perilaku bawaan Apps Script).
            with urllib.request.urlopen(err.headers["Location"], timeout=20) as echo:
                body = echo.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, "Server panitia sedang tidak bisa dihubungi. Coba lagi sebentar lagi ya."

    try:
        hasil = json.loads(body)
    except ValueError:
        return False, "Balasan server panitia tidak terbaca. Coba sekali lagi."
    if hasil.get("status") == "success":
        return True, str(hasil.get("message") or "Pendaftaran berhasil dicatat.")
    return False, str(hasil.get("message") or "Pendaftaran ditolak server panitia.")
