"""
Nordelia Real-Time Google Spreadsheet & Local Storage Service
SMA Ignatius Global School (IGS) Palembang - Kabinet Orvelion 2026-2027

Fitur:
1. Pembacaan konfigurasi aman dari .env (tanpa dependensi eksternal)
2. Klasifikasi otomatis pendaftaran berdasarkan kategori lomba (Akademik, Bahasa, Seni, Olahraga)
3. Sinkronisasi real-time ke Google Spreadsheet (via Google Apps Script Webhook)
4. Pengambilan data real-time langsung dari Google Spreadsheet dengan smart in-memory TTL caching
5. Persistensi lokal instan (SQLite & JSON) sebagai cadangan andal jika jaringan offline
6. Ekspor data ke format CSV dan tabel interaktif real-time
"""

import csv
import io
import json
import os
import sqlite3
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from orvelion.nordelia_data import CABANG_LOMBA, SHEET2_FORMAT_SPEC, get_cabang_by_id

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
DB_PATH = os.path.join(BASE_DIR, "nordelia.db")
JSON_PATH = os.path.join(BASE_DIR, "nordelia_registrations.json")


def load_env_file(filepath: str = ENV_PATH) -> Dict[str, str]:
    """Membaca file .env secara aman tanpa dependensi tambahan."""
    env_vars = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        env_vars[k] = v
                        os.environ[k] = v
        except Exception as e:
            print(f"[ENV] Gagal membaca file .env: {e}")
    return env_vars


# Muat variabel environment saat modul diimpor
load_env_file()


def get_config(key: str, default: str = "") -> str:
    """Mengambil nilai konfigurasi dari os.environ atau file .env."""
    return os.environ.get(key, default)


def _ssl_context() -> ssl.SSLContext:
    """Python.org di macOS sering tidak punya CA bundle default; pakai certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _normalize_key(s: str) -> str:
    if not s:
        return ""
    return "".join(c for c in str(s).lower() if c.isalnum())


def _get_cabang_lookup() -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for c in CABANG_LOMBA:
        lookup[_normalize_key(c.get("name", ""))] = c
        lookup[_normalize_key(c.get("sheet_name", ""))] = c
        lookup[_normalize_key(c.get("id", ""))] = c

    # Alias populer untuk AI dan Olimpiade
    ai_cb = get_cabang_by_id("olimpiade-ai") or {}
    if ai_cb:
        lookup[_normalize_key("olimpiade kecerdasan artifisial")] = ai_cb
        lookup[_normalize_key("olimpiade ai")] = ai_cb
        lookup[_normalize_key("kecerdasan artifisial")] = ai_cb
        lookup[_normalize_key("ai")] = ai_cb

    return lookup


class NordeliaStorage:
    """
    Mengelola sinkronisasi Google Spreadsheet Real-Time dan penyimpanan lokal (SQLite & JSON).
    Data kuota dan jumlah pendaftar diambil langsung dari Google Spreadsheet dengan sistem caching pintar.
    """

    CACHE_TTL_SECONDS = 8.0  # 8 detik TTL: Cepat, responsif, dan tidak membebani Google

    def __init__(self, db_path: str = DB_PATH, json_path: str = JSON_PATH):
        self.db_path = db_path
        self.json_path = json_path
        self._cache_lock = threading.Lock()
        self._sheet_cache: Dict[str, Any] = {
            "timestamp": 0.0,
            "registrations": [],
            "counts": {},
            "summary": None,
        }
        self._init_db()

    def _connect(self):
        """Koneksi SQLite dengan mode konkurensi tinggi (WAL).

        Non-fungsional: skema tabel, data, dan hasil query TIDAK berubah.
        Yang berubah hanya mode jurnal + ketahanan terhadap kuncian:
        - journal_mode=WAL : penulis tidak lagi memblokir pembaca (dan
          sebaliknya) — saat event ramai, penyimpanan pendaftaran baru
          (POST) berjalan paralel dengan pembacaan kuota/statistik (GET).
        - busy_timeout=5000 : dua penulisan bersamaan otomatis menunggu
          antre (bukan langsung error "database is locked").
        - synchronous=NORMAL : aman bersama WAL dan jauh lebih cepat.
        (queue.py memakai file DB yang sama dan sudah memakai pengaturan
        identik — kini selaras di seluruh aplikasi.)
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        try:
            conn = self._connect()
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    cabang_id TEXT NOT NULL,
                    cabang_name TEXT NOT NULL,
                    participant_name TEXT NOT NULL,
                    kelas TEXT NOT NULL,
                    whatsapp TEXT,
                    details_json TEXT,
                    synced_to_sheets INTEGER DEFAULT 0
                )
            """)
            # Index untuk mempercepat agregasi kuota/statistik per cabang & kategori
            # (struktur tabel dan data tidak berubah sama sekali)
            c.execute("CREATE INDEX IF NOT EXISTS idx_registrations_cabang ON registrations(cabang_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_registrations_category ON registrations(category_id)")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal inisialisasi SQLite: {e}")

    def invalidate_cache(self):
        """Mereset cache agar pembacaan berikutnya langsung meminta data terbaru dari Google Sheet."""
        with self._cache_lock:
            self._sheet_cache["timestamp"] = 0.0

    def fetch_from_google_sheet(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Mengambil pendaftaran dan hitungan kuota langsung dari Google Spreadsheet secara real-time.
        Jika Google Sheet tidak dapat dihubungi (timeout/offline), akan otomatis fallback ke data lokal.
        """
        now = time.time()
        with self._cache_lock:
            if not force_refresh and (now - self._sheet_cache["timestamp"] < self.CACHE_TTL_SECONDS) and self._sheet_cache["registrations"]:
                return {
                    "registrations": self._sheet_cache["registrations"],
                    "counts": self._sheet_cache["counts"],
                    "summary": self._sheet_cache["summary"],
                    "source": "google_sheet_cache",
                }

        spreadsheet_id = get_config("NORDELIA_SPREADSHEET_ID")
        if not spreadsheet_id:
            return None

        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=Master%20Pendaftaran"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OrvelionPortal/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=4, context=_ssl_context()) as resp:
                content = resp.read().decode("utf-8", errors="replace")

            reader = csv.reader(io.StringIO(content))
            rows = list(reader)

            lookup = _get_cabang_lookup()
            items: List[Dict[str, Any]] = []
            counts: Dict[str, int] = {}

            # Parse setiap baris pendaftaran di Master Pendaftaran
            for idx, r in enumerate(rows):
                if not r or not any(r):
                    continue
                first_cell = r[0].strip().upper()
                if "WAKTU" in first_cell or "SEMUA PENDAFTARAN" in first_cell or "MASTER" in first_cell:
                    continue
                if len(r) < 4:
                    continue

                timestamp = r[0].strip()
                raw_cat = r[1].strip().lower() if len(r) > 1 else "akademik"
                cabang_raw = r[2].strip() if len(r) > 2 else ""
                nama = r[3].strip() if len(r) > 3 else ""
                kelas = r[4].strip() if len(r) > 4 else "-"
                whatsapp = r[5].strip() if len(r) > 5 else "-"
                detail_raw = r[6].strip() if len(r) > 6 else ""

                if not nama or not cabang_raw:
                    continue

                cb = lookup.get(_normalize_key(cabang_raw))
                cid = cb["id"] if cb else cabang_raw.lower().replace(" ", "-")
                cname = cb["name"] if cb else cabang_raw
                cat_id = cb["category"].lower() if cb else raw_cat

                # Update hitungan per cabang
                counts[cid] = counts.get(cid, 0) + 1
                if cb and cb.get("id") and cb["id"] != cid:
                    counts[cb["id"]] = counts.get(cb["id"], 0) + 1

                # Parse details
                details_dict = {"raw": detail_raw}
                if detail_raw and ":" in detail_raw:
                    try:
                        for part in detail_raw.split(" | "):
                            if ":" in part:
                                pk, pv = part.split(":", 1)
                                details_dict[pk.strip()] = pv.strip()
                    except Exception:
                        pass

                items.append({
                    "id": len(rows) - idx,
                    "created_at": timestamp,
                    "category_id": cat_id,
                    "cabang_id": cid,
                    "cabang_name": cname,
                    "participant_name": nama,
                    "kelas": kelas,
                    "whatsapp": whatsapp,
                    "details": details_dict,
                    "synced_to_sheets": True,
                })

            summary = {
                "counts": {
                    "total": len(items),
                    "akademik": sum(1 for r in items if r.get("category_id") == "akademik"),
                    "bahasa": sum(1 for r in items if r.get("category_id") == "bahasa"),
                    "seni": sum(1 for r in items if r.get("category_id") == "seni"),
                    "cosplay": sum(1 for r in items if r.get("category_id") == "cosplay"),
                    "olahraga": sum(1 for r in items if r.get("category_id") == "olahraga"),
                },
                "latest": items[:5],
                "total_cabang": len(CABANG_LOMBA),
            }

            with self._cache_lock:
                self._sheet_cache["timestamp"] = time.time()
                self._sheet_cache["registrations"] = items
                self._sheet_cache["counts"] = counts
                self._sheet_cache["summary"] = summary

            return {
                "registrations": items,
                "counts": counts,
                "summary": summary,
                "source": "google_sheet_live",
            }
        except Exception as e:
            print(f"[SHEETS-FETCH] Google Sheet tidak merespons (menggunakan cache/lokal): {e}")
            with self._cache_lock:
                if self._sheet_cache["registrations"]:
                    return {
                        "registrations": self._sheet_cache["registrations"],
                        "counts": self._sheet_cache["counts"],
                        "summary": self._sheet_cache["summary"],
                        "source": "google_sheet_stale_cache",
                    }
            return None

    def save_registration(self, reg_data: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cabang_info = get_cabang_by_id(reg_data.get("cabang_id", ""))

        if cabang_info and cabang_info.get("category"):
            category_id = cabang_info["category"].lower()
        else:
            raw_cat = (reg_data.get("category_id") or "").lower()
            if any(k in raw_cat for k in ["akademik", "olimp", "sains", "science", "numerasi"]):
                category_id = "akademik"
            elif any(k in raw_cat for k in ["bahasa", "debat", "ldbi", "nsdc", "story"]):
                category_id = "bahasa"
            elif any(k in raw_cat for k in ["seni", "fls3n", "kriya", "puisi", "poster", "vokal", "lagu"]):
                category_id = "seni"
            elif any(k in raw_cat for k in ["olahraga", "o2sn", "basket", "futsal", "voli", "atletik", "silat", "catur"]):
                category_id = "olahraga"
            else:
                category_id = "akademik"

        cabang_name = reg_data.get("cabang_name") or (cabang_info["name"] if cabang_info else reg_data.get("cabang_id", ""))
        sheet_name = (cabang_info.get("sheet_name") if cabang_info else None) or cabang_name
        participant_name = reg_data.get("nama_lengkap") or reg_data.get("nama_tim") or reg_data.get("nama", "Anonim")
        kelas = reg_data.get("kelas", "-")
        whatsapp = reg_data.get("whatsapp", "-")

        entry = {
            "id": None,
            "created_at": timestamp,
            "category_id": category_id,
            "cabang_id": reg_data.get("cabang_id", ""),
            "cabang_name": cabang_name,
            "sheet_name": sheet_name,
            "participant_name": participant_name,
            "kelas": kelas,
            "whatsapp": whatsapp,
            "details": reg_data,
            "synced_to_sheets": False,
        }

        # Simpan ke SQLite
        try:
            conn = self._connect()
            c = conn.cursor()
            c.execute("""
                INSERT INTO registrations (
                    created_at, category_id, cabang_id, cabang_name,
                    participant_name, kelas, whatsapp, details_json, synced_to_sheets
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                category_id,
                entry["cabang_id"],
                cabang_name,
                participant_name,
                kelas,
                whatsapp,
                json.dumps(reg_data, ensure_ascii=False),
                0,
            ))
            entry["id"] = c.lastrowid
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal insert sqlite: {e}")
            entry["id"] = int(time.time() * 1000) % 1000000

        # Simpan juga ke file JSON sebagai cadangan
        self._append_json(entry)

        # Trigger sinkronisasi real-time ke Google Spreadsheet
        sync_ok = push_to_google_sheet(entry)
        if sync_ok and entry["id"]:
            self._mark_synced(entry["id"])
            entry["synced_to_sheets"] = True

        # Invalidate cache agar request berikutnya langsung mengambil data baru dari Google Sheet
        self.invalidate_cache()

        return entry

    def _get_unsynced_registrations(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Entri lokal yang belum berhasil masuk Google Sheet (untuk retry).
        Query langsung dengan flag synced_to_sheets=0 — tidak memuat seluruh
        tabel, aman dipanggil berkala oleh thread background."""
        results: List[Dict[str, Any]] = []
        try:
            conn = self._connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if limit is not None:
                c.execute(
                    "SELECT * FROM registrations WHERE synced_to_sheets = 0 ORDER BY id ASC LIMIT ?",
                    (int(limit),),
                )
            else:
                c.execute("SELECT * FROM registrations WHERE synced_to_sheets = 0 ORDER BY id ASC")
            rows = c.fetchall()
            for r in rows:
                results.append(self._row_to_registration(r))
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal query unsynced: {e}")
        return results

    def retry_unsynced(self, limit: Optional[int] = None) -> int:
        """Kirim ulang pendaftaran lokal yang belum masuk Google Sheet.

        limit: batas jumlah entri per putaran (None = semua). Dipanggil
        otomatis oleh thread background (lihat optimizations.py) setiap
        5 menit dengan limit 50 — pendaftaran yang gagal terkirim karena
        gangguan jaringan akan self-heal tanpa campur tangan panitia.
        """
        sent = 0
        for entry in self._get_unsynced_registrations(limit):
            if push_to_google_sheet(entry):
                self._mark_synced(entry["id"])
                sent += 1
        if sent > 0:
            self.invalidate_cache()
        return sent

    def _mark_synced(self, reg_id: int):
        try:
            conn = self._connect()
            c = conn.cursor()
            c.execute("UPDATE registrations SET synced_to_sheets = 1 WHERE id = ?", (reg_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal update sync status: {e}")
        self._mark_json_synced(reg_id)

    def _mark_json_synced(self, reg_id: int):
        if not os.path.exists(self.json_path):
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                items = json.load(f)
            changed = False
            for item in items:
                if item.get("id") == reg_id and not item.get("synced_to_sheets"):
                    item["synced_to_sheets"] = True
                    changed = True
            if changed:
                with open(self.json_path, "w", encoding="utf-8") as f:
                    json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[JSON] Gagal update sync status: {e}")

    def _append_json(self, entry: Dict[str, Any]):
        items = []
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
            except Exception:
                items = []
        items.append(entry)
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[JSON] Gagal simpan json: {e}")

    def delete_registration(self, reg_id: int) -> bool:
        deleted = False
        try:
            conn = self._connect()
            c = conn.cursor()
            c.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
            conn.commit()
            if c.rowcount > 0:
                deleted = True
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal delete sqlite: {e}")

        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                new_items = [i for i in items if str(i.get("id")) != str(reg_id)]
                if len(new_items) != len(items):
                    deleted = True
                    with open(self.json_path, "w", encoding="utf-8") as f:
                        json.dump(new_items, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[JSON] Gagal delete json: {e}")

        self.invalidate_cache()
        return deleted

    def _row_to_registration(self, r) -> Dict[str, Any]:
        """Mapping satu baris SQLite ke dict pendaftaran (dipakai semua query)."""
        details = {}
        try:
            details = json.loads(r["details_json"])
        except Exception:
            pass
        return {
            "id": r["id"],
            "created_at": r["created_at"],
            "category_id": r["category_id"],
            "cabang_id": r["cabang_id"],
            "cabang_name": r["cabang_name"],
            "participant_name": r["participant_name"],
            "kelas": r["kelas"],
            "whatsapp": r["whatsapp"],
            "details": details,
            "synced_to_sheets": bool(r["synced_to_sheets"]),
        }

    def _get_local_registrations(self, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        try:
            conn = self._connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if category_id and category_id.lower() != "semua":
                c.execute(
                    "SELECT * FROM registrations WHERE LOWER(category_id) = ? ORDER BY id DESC",
                    (category_id.lower(),),
                )
            else:
                c.execute("SELECT * FROM registrations ORDER BY id DESC")
            rows = c.fetchall()
            for r in rows:
                results.append(self._row_to_registration(r))
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal query sqlite: {e}")
            if os.path.exists(self.json_path):
                try:
                    with open(self.json_path, "r", encoding="utf-8") as f:
                        items = json.load(f)
                        if category_id and category_id.lower() != "semua":
                            results = [i for i in items if i.get("category_id", "").lower() == category_id.lower()]
                        else:
                            results = items
                except Exception:
                    results = []
        return results

    def _get_local_counts_by_cabang(self) -> Dict[str, int]:
        # Optimasi: agregasi GROUP BY langsung di SQL (hasil identik dengan
        # menghitung baris satu per satu di Python, tanpa memuat seluruh isi
        # tabel + parse details_json pada setiap request).
        counts: Dict[str, int] = {}
        try:
            conn = self._connect()
            c = conn.cursor()
            grouped = c.execute(
                "SELECT cabang_id, COUNT(*) FROM registrations "
                "WHERE cabang_id IS NOT NULL AND cabang_id != '' "
                "GROUP BY cabang_id"
            ).fetchall()
            conn.close()
            for cid, n in grouped:
                counts[cid] = n
                cb = get_cabang_by_id(cid)
                if cb and cb["id"] != cid:
                    counts[cb["id"]] = counts.get(cb["id"], 0) + n
            return counts
        except Exception as e:
            print(f"[DB] Gagal hitung per cabang (fallback ke Python): {e}")

        counts = {}
        all_regs = self._get_local_registrations()
        for r in all_regs:
            cid = r.get("cabang_id")
            if cid:
                counts[cid] = counts.get(cid, 0) + 1
                cb = get_cabang_by_id(cid)
                if cb and cb["id"] != cid:
                    counts[cb["id"]] = counts.get(cb["id"], 0) + 1
        return counts

    def _get_local_summary_stats(self) -> Dict[str, Any]:
        # Optimasi: hitungan kategori via GROUP BY + 5 data terakhir via LIMIT,
        # tanpa memuat seluruh tabel ke memori (hasil identik).
        try:
            conn = self._connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            grouped = c.execute(
                "SELECT LOWER(category_id) AS cat, COUNT(*) AS n FROM registrations "
                "GROUP BY LOWER(category_id)"
            ).fetchall()
            by_cat = {row["cat"]: row["n"] for row in grouped}
            latest_rows = c.execute(
                "SELECT * FROM registrations ORDER BY id DESC LIMIT 5"
            ).fetchall()
            conn.close()
            return {
                "counts": {
                    "total": sum(by_cat.values()),
                    "akademik": by_cat.get("akademik", 0),
                    "bahasa": by_cat.get("bahasa", 0),
                    "seni": by_cat.get("seni", 0),
                    "cosplay": by_cat.get("cosplay", 0),
                    "olahraga": by_cat.get("olahraga", 0),
                },
                "latest": [self._row_to_registration(r) for r in latest_rows],
                "total_cabang": len(CABANG_LOMBA),
            }
        except Exception as e:
            print(f"[DB] Gagal ringkasan statistik (fallback ke Python): {e}")

        all_regs = self._get_local_registrations()
        counts = {
            "total": len(all_regs),
            "akademik": sum(1 for r in all_regs if r.get("category_id") == "akademik"),
            "bahasa": sum(1 for r in all_regs if r.get("category_id") == "bahasa"),
            "seni": sum(1 for r in all_regs if r.get("category_id") == "seni"),
            "cosplay": sum(1 for r in all_regs if r.get("category_id") == "cosplay"),
            "olahraga": sum(1 for r in all_regs if r.get("category_id") == "olahraga"),
        }
        return {
            "counts": counts,
            "latest": all_regs[:5],
            "total_cabang": len(CABANG_LOMBA),
        }

    # =========================================================================
    # PUBLIC ACCESSORS: Mengutamakan Google Spreadsheet Real-Time
    # =========================================================================

    def get_counts_by_cabang(self, force_refresh: bool = False) -> Dict[str, int]:
        """Mengembalikan jumlah pendaftar per cabang secara real-time langsung dari database lokal."""
        return self._get_local_counts_by_cabang()

    def get_cabang_count(self, cabang_id: str, force_refresh: bool = False) -> int:
        """Mengambil total pendaftar spesifik untuk 1 cabang lomba secara real-time."""
        counts = self.get_counts_by_cabang(force_refresh=force_refresh)
        return counts.get(cabang_id, 0)

    def get_summary_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Statistik ringkasan pendaftaran secara real-time langsung dari database."""
        return self._get_local_summary_stats()

    def get_all_registrations(self, category_id: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Mengambil seluruh data pendaftar secara real-time langsung dari database."""
        return self._get_local_registrations(category_id)


# Inisialisasi instance storage
storage = NordeliaStorage()


def push_to_google_sheet(entry: Dict[str, Any]) -> bool:
    """
    Sinkronisasi real-time ke Google Spreadsheet via Google Apps Script Webhook.
    """
    load_env_file()
    webhook_url = get_config("GOOGLE_SHEET_WEBHOOK_URL")
    sheet_id = get_config("NORDELIA_SPREADSHEET_ID")

    if webhook_url and webhook_url.startswith("http"):
        try:
            target_sheet = entry.get("sheet_name") or entry.get("cabang_name") or "Lomba"
            payload = {
                "action": "register",
                "spreadsheet_id": sheet_id,
                "timestamp": entry.get("created_at"),
                "category": entry.get("category_id", "").upper(),
                "target_sheet": target_sheet,
                "cabang": entry.get("cabang_name"),
                "nama": entry.get("participant_name"),
                "kelas": entry.get("kelas"),
                "kontak": entry.get("whatsapp"),
                "detail": entry.get("details", {}),
            }
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OrvelionBot/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status in (200, 201, 302, 303):
                    if '"status":"error"' in body.replace(" ", ""):
                        print(f"[SHEETS-WEBHOOK] Apps Script error: {body[:400]}")
                        return False
                    return True
        except Exception as e:
            print(f"[SHEETS-WEBHOOK] Gagal push real-time ke Google Apps Script: {e}")

    return False


def export_registrations_csv(category_id: Optional[str] = None) -> str:
    """Mengekspor pendaftaran ke string CSV standar langsung dari data Google Sheet."""
    regs = storage.get_all_registrations(category_id)
    output = io.StringIO()
    writer = csv.writer(output)

    # Header CSV
    writer.writerow([
        "ID",
        "Waktu Pendaftaran",
        "Kategori",
        "Cabang Lomba",
        "Nama Peserta / Tim",
        "Kelas",
        "Nomor WhatsApp / Kontak",
        "Detail Tambahan / Format Spesifik",
        "Status Sinkronisasi Spreadsheet",
    ])

    for r in regs:
        details_str = json.dumps(r.get("details", {}), ensure_ascii=False)
        writer.writerow([
            r.get("id"),
            r.get("created_at"),
            r.get("category_id", "").capitalize(),
            r.get("cabang_name"),
            r.get("participant_name"),
            r.get("kelas"),
            r.get("whatsapp"),
            details_str,
            "Tersinkron Google Sheet" if r.get("synced_to_sheets") else "Tersimpan Lokal",
        ])

    return output.getvalue()
