"""Pendaftaran lomba Nordelia 2026 — jembatan situs -> Google Spreadsheet.

Alur: form di /daftar -> validasi di server (sini) -> diteruskan ke webhook
Google Apps Script milik panitia -> masuk sheet "Master Pendaftaran" + sheet
per cabang lomba (nama tab ditentukan field "target_sheet", selaras dengan
DAFTAR_CABANG_LOMBA di Code.gs — cek dengan tools/cek-konsistensi.py).

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
#
# Penamaan tab spreadsheet:
# - "sheet"      : nama tab untuk lomba tanpa sub (default = nama lomba).
# - "sheet_fmt"  : pola nama tab untuk lomba bersub (cth. "Olimpiade {}").
# - "sheet_map"  : pemetaan sub -> nama tab untuk yang tidak mengikuti pola.
# Nama-nama ini HARUS sama dengan DAFTAR_CABANG_LOMBA di Code.gs.
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
                "sheet_fmt": "Olimpiade {}",
            },
            {
                "id": "olimpiade-ai",
                "nama": "Olimpiade Kecerdasan Artifisial (AI)",
                "sheet": "Olimpiade Kecerdasan Artifisial",
            },
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
                "sheet_fmt": "{}",
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
                "sheet_map": {
                    "Bahasa Jerman": "Olimpiade Bahasa Jerman",
                    "Bahasa Jepang": "Olimpiade Bahasa Jepang",
                    "Bahasa Korea": "Olimpiade Bahasa Korea",
                    "Bahasa Mandarin": "Olimpiade Bahasa Mandarin",
                    "Bahasa Spanyol": "Olimpiade Bahasa Spanyol",
                    "Bahasa Prancis": "Olimpiade Bahasa Prancis",
                    "Bahasa Arab": "Olimpiade Bahasa Arab",
                    "Kaligrafi": "Kaligrafi Bahasa Arab",
                    "Menyanyi Mandarin": "Menyanyi Bahasa Mandarin",
                    "Cosplay": "Cosplay",
                    "Story Telling": "Story Telling Korea",
                },
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
                "subs": ["Baca Puisi", "Cipta Puisi", "Cerita Pendek", "Monolog", "Poster", "Gitar", "Menyanyi Solo Putra", "Menyanyi Solo Putri", "Kriya", "Komik", "Tari"],
                "cabang_fmt": "FLS3N {}",
                "sheet_map": {
                    "Cerita Pendek": "Menulis Cerpen",
                    "Poster": "Desain Poster",
                    "Gitar": "Instrumen Solo Gitar",
                    "Komik": "Komik Digital",
                    "Tari": "Tari Kreasi",
                },
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
                "sheet_fmt": "{}",
            },
        ],
    },
]

# Kuota resmi panitia: 10 cabang Olimpiade (9 sains + Kecerdasan Artifisial)
# dibatasi maksimal 20 peserta per cabang. Ditegakkan di Code.gs saat menulis
# baris (sumber kebenaran); situs memakainya untuk menampilkan sisa tempat.
KUOTA_CABANG = {
    "Olimpiade Matematika": 20,
    "Olimpiade Fisika": 20,
    "Olimpiade Kimia": 20,
    "Olimpiade Biologi": 20,
    "Olimpiade Astronomi": 20,
    "Olimpiade Geografi": 20,
    "Olimpiade Informatika": 20,
    "Olimpiade Ekonomi": 20,
    "Olimpiade Kebumian": 20,
    "Olimpiade Kecerdasan Artifisial": 20,
}

# Saran isian kelas (tetap bebas diketik manual — ini cuma bantuan).
KELAS_CONTOH = [
    "10.1 CGC", "10.2 MAYOR", "10.3 MAYOR",
    "11.1 CGC", "11.2 CGC", "11.1 MAYOR", "11.2 MAYOR",
    "12.1 CGC", "12.2 MAYOR",
]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _sheet_name(lomba: dict[str, Any], sub: str | None, cabang_name: str) -> str:
    """Nama tab spreadsheet panitia untuk cabang ini (selaras Code.gs)."""
    if not lomba.get("subs"):
        return str(lomba.get("sheet") or cabang_name)
    peta = lomba.get("sheet_map") or {}
    if sub in peta:
        return str(peta[sub])
    fmt = lomba.get("sheet_fmt")
    if fmt:
        return fmt.format(sub) if "{}" in fmt else str(fmt)
    return str(sub or cabang_name)


def _indeks_cabang() -> dict[str, dict[str, Any]]:
    """cabang_id -> {kategori, lomba, sub, cabang_name, sheet, extra}."""
    indeks: dict[str, dict[str, Any]] = {}
    for kat in KATEGORI_LOMBA:
        for lomba in kat["lomba"]:
            subs = lomba.get("subs")
            if not subs:
                nama = lomba["nama"]
                indeks[_slug(nama)] = {
                    "kategori": kat, "lomba": lomba, "sub": None, "cabang_name": nama,
                    "sheet": _sheet_name(lomba, None, nama),
                }
                continue
            fmt = lomba.get("cabang_fmt", "{}")
            for sub in subs:
                cabang_name = fmt.format(sub) if "{}" in fmt else fmt
                indeks[_slug(cabang_name)] = {
                    "kategori": kat, "lomba": lomba, "sub": sub, "cabang_name": cabang_name,
                    "sheet": _sheet_name(lomba, sub, cabang_name),
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
        "target_sheet": info["sheet"],
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
            # Sub pilihan pengguna menentukan tab tujuan (LDBI/NSDC punya
            # sheet terpisah) — jangan pakai sub dari indeks (bisa tertukar
            # karena cabang_id debat sama untuk kedua jenisnya).
            payload["target_sheet"] = _sheet_name(info["lomba"], sub, info["cabang_name"])
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


def kirim_ke_webhook(payload: dict[str, Any], antrikan: bool = True) -> tuple[bool, str, bool]:
    """Kirim payload ke Apps Script.

    Mengembalikan (sukses, pesan, mengantre). Kegagalan jaringan/parsing
    tidak dibuang: payload masuk antrian lokal dan dikirim ulang otomatis
    (kecuali `antrikan=False`, dipakai pekerja antrian supaya tidak dobel).
    Kegagal "resmi" dari Apps Script (cth. kuota penuh) TIDAK diantrikan.
    """
    url = webhook_url()
    if not webhook_aktif():
        return False, "Pendaftaran online belum dikonfigurasi panitia (GOOGLE_SHEET_WEBHOOK_URL kosong).", False

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
        if antrikan and antrian_tambah(payload):
            return True, ("Koneksi ke server panitia sedang terganggu. Pendaftaranmu "
                          "sudah tersimpan dan otomatis dikirim ulang — tidak perlu "
                          "mengisi ulang."), True
        return False, "Server panitia sedang tidak bisa dihubungi. Coba lagi sebentar lagi ya.", False

    try:
        hasil = json.loads(body)
    except ValueError:
        if antrikan and antrian_tambah(payload):
            return True, ("Balasan server panitia belum terbaca. Pendaftaranmu "
                          "sudah tersimpan dan otomatis dicoba ulang."), True
        return False, "Balasan server panitia tidak terbaca. Coba sekali lagi.", False
    if hasil.get("status") == "success":
        return True, str(hasil.get("message") or "Pendaftaran berhasil dicatat."), False
    return False, str(hasil.get("message") or "Pendaftaran ditolak server panitia."), False


# --------------------------------------------------------------------------
# Antrian kirim-ulang — pendaftaran tidak boleh hilang cuma karena webhook
# sedang gangguan. Payload yang gagal terkirim disimpan di file lokal
# (nordelia_antrian.json, sudah di-gitignore) lalu dicoba ulang otomatis.
# ---------------------------------------------------------------------------

ANTRIAN_PATH = os.path.join(os.path.dirname(__file__), "..", "nordelia_antrian.json")
_ANTRIAN_LOCK = threading.Lock()
_ANTRIAN_INTERVAL = 300.0   # pekerja memeriksa antrian tiap 5 menit
_pekerja_sudah_mulai = False


def _antrian_baca() -> list[dict[str, Any]]:
    try:
        with open(ANTRIAN_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _antrian_tulis(items: list[dict[str, Any]]) -> None:
    # Tulis lewat file sementara supaya list tidak rusak kalau proses mati
    # di tengah penulisan.
    sementara = f"{ANTRIAN_PATH}.tmp"
    with open(sementara, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=1)
    os.replace(sementara, ANTRIAN_PATH)


def antrian_tambah(payload: dict[str, Any]) -> bool:
    with _ANTRIAN_LOCK:
        try:
            items = _antrian_baca()
            items.append({"payload": payload, "sejak": time.strftime("%Y-%m-%d %H:%M:%S")})
            _antrian_tulis(items)
            return True
        except OSError:
            return False


def proses_antrian(pengirim=None) -> int:
    """Kirim ulang semua yang mengantre. Mengembalikan jumlah yang berhasil."""
    kirim = pengirim or (lambda p: kirim_ke_webhook(p, antrikan=False))
    with _ANTRIAN_LOCK:
        items = _antrian_baca()
    if not items:
        return 0
    tersisa: list[dict[str, Any]] = []
    terkirim = 0
    for item in items:
        payload = item.get("payload") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            continue  # entri rusak: buang saja
        try:
            sukses, _pesan = kirim(payload)
        except Exception:  # noqa: BLE001 — jangan sampai satu entri mematikan pekerja
            sukses = False
        if sukses:
            terkirim += 1
        else:
            tersisa.append(item)
    with _ANTRIAN_LOCK:
        try:
            _antrian_tulis(tersisa)
        except OSError:
            pass
    return terkirim


def _pekerja_antrian() -> None:
    while True:
        time.sleep(_ANTRIAN_INTERVAL)
        try:
            proses_antrian()
        except Exception:  # noqa: BLE001
            pass


def mulai_pekerja_antrian() -> None:
    """Jalankan pekerja kirim-ulang di latar belakang (sekali per proses)."""
    global _pekerja_sudah_mulai
    if _pekerja_sudah_mulai:
        return
    _pekerja_sudah_mulai = True
    threading.Thread(target=_pekerja_antrian, daemon=True, name="nordelia-antrian").start()


# --------------------------------------------------------------------------
# Sisa kuota per cabang — dibaca dari endpoint ?counts=1 Apps Script,
# di-cache 60 detik supaya formulir tidak membebani webhook.
# ---------------------------------------------------------------------------

_KUOTA_LOCK = threading.Lock()
_KUOTA_CACHE: dict[str, Any] = {"saat": 0.0, "isi": None}
_KUOTA_TTL = 60.0


def _http_get_json(url: str) -> dict[str, Any] | None:
    opener = urllib.request.build_opener(_TanpaRedirect())
    try:
        try:
            dengan = opener.open(urllib.request.Request(url), timeout=20)
            body = dengan.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            if err.code not in (301, 302, 303, 307, 308) or not err.headers.get("Location"):
                raise
            with urllib.request.urlopen(err.headers["Location"], timeout=20) as echo:
                body = echo.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def ambil_kuota(paksa: bool = False) -> dict[str, dict[str, int]] | None:
    """Sisa kuota cabang berkuota: {nama_sheet: {"terpakai": n, "maks": m}}.

    Sumber kebenaran tetap Code.gs; hasil di-cache 60 detik. None berarti
    webhook belum aktif / tidak bisa dihubungi (formulir tetap jalan,
    penegakan kuota tetap terjadi di Apps Script saat pendaftaran masuk).
    """
    if not webhook_aktif():
        return None
    kini = time.time()
    with _KUOTA_LOCK:
        if (not paksa and _KUOTA_CACHE["isi"] is not None
                and kini - _KUOTA_CACHE["saat"] < _KUOTA_TTL):
            return _KUOTA_CACHE["isi"]

    hasil = _http_get_json(webhook_url() + "?counts=1")
    if not hasil or hasil.get("status") != "ok" or not isinstance(hasil.get("counts"), dict):
        # Gagal ambil -> pakai cache lama kalau masih ada (kuota basi lebih
        # baik daripada form error; kebenaran akhir tetap di Apps Script).
        with _KUOTA_LOCK:
            return _KUOTA_CACHE["isi"]

    hitungan = hasil["counts"]
    isi: dict[str, dict[str, int]] = {}
    for sheet, maks in KUOTA_CABANG.items():
        try:
            terpakai = max(0, int(hitungan.get(sheet, 0)))
        except (TypeError, ValueError):
            terpakai = 0
        isi[sheet] = {"terpakai": terpakai, "maks": int(maks)}
    with _KUOTA_LOCK:
        _KUOTA_CACHE["saat"] = time.time()
        _KUOTA_CACHE["isi"] = isi
    return isi
