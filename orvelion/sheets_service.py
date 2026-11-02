"""
Nordelia Real-Time Google Spreadsheet & Local Storage Service
SMA Ignatius Global School (IGS) Palembang - Kabinet Orvelion 2026-2027

Fitur:
1. Pembacaan konfigurasi aman dari .env (tanpa dependensi eksternal)
2. Klasifikasi otomatis pendaftaran berdasarkan kategori lomba (Akademik, Bahasa, Seni, Olahraga)
3. Sinkronisasi real-time ke Google Spreadsheet (via Google Service Account / Google Sheets API v4 atau Google Apps Script Webhook)
4. Persistensi lokal instan (JSON & SQLite) sehingga data pendaftaran aman, tidak hilang, dan tabel live spreadsheet selalu responsif
5. Ekspor data ke format CSV dan tabel interaktif real-time
"""

import csv
import io
import json
import os
import sqlite3
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


class NordeliaStorage:
    """Mengelola penyimpanan lokal (SQLite & JSON) untuk pendaftaran Nordelia."""

    def __init__(self, db_path: str = DB_PATH, json_path: str = JSON_PATH):
        self.db_path = db_path
        self.json_path = json_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
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
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal inisialisasi SQLite: {e}")

    def save_registration(self, reg_data: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cabang_info = get_cabang_by_id(reg_data.get("cabang_id", ""))
        
        # Normalisasi kategori ke 4 bidang utama: akademik, bahasa, seni, olahraga
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
            conn = sqlite3.connect(self.db_path)
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

        return entry

    def _mark_synced(self, reg_id: int):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("UPDATE registrations SET synced_to_sheets = 1 WHERE id = ?", (reg_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal update sync status: {e}")

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

    def get_all_registrations(self, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
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
                details = {}
                try:
                    details = json.loads(r["details_json"])
                except Exception:
                    pass
                results.append({
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
                })
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal query sqlite: {e}")
            # Fallback ke JSON jika sqlite gagal
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

    def get_cabang_count(self, cabang_id: str) -> int:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM registrations WHERE cabang_id = ?', (cabang_id,))
            res = c.fetchone()
            conn.close()
            return res[0] if res else 0
        except Exception:
            regs = self.get_all_registrations()
            return sum(1 for r in regs if r.get('cabang_id') == cabang_id)

    def get_counts_by_cabang(self) -> Dict[str, int]:
        counts = {}
        all_regs = self.get_all_registrations()
        for r in all_regs:
            cid = r.get("cabang_id")
            if cid:
                counts[cid] = counts.get(cid, 0) + 1
                cb = get_cabang_by_id(cid)
                if cb and cb["id"] != cid:
                    counts[cb["id"]] = counts.get(cb["id"], 0) + 1
        return counts

    def get_summary_stats(self) -> Dict[str, Any]:
        all_regs = self.get_all_registrations()
        counts = {
            "total": len(all_regs),
            "akademik": sum(1 for r in all_regs if r.get("category_id") == "akademik"),
            "bahasa": sum(1 for r in all_regs if r.get("category_id") == "bahasa"),
            "seni": sum(1 for r in all_regs if r.get("category_id") == "seni"),
            "olahraga": sum(1 for r in all_regs if r.get("category_id") == "olahraga"),
        }
        return {
            "counts": counts,
            "latest": all_regs[:5],
            "total_cabang": len(CABANG_LOMBA),
        }


# Inisialisasi instance storage
storage = NordeliaStorage()


def push_to_google_sheet(entry: Dict[str, Any]) -> bool:
    """
    Sinkronisasi real-time ke Google Spreadsheet:
    1. Menggunakan Google Apps Script Webhook (jika GOOGLE_SHEET_WEBHOOK_URL terpasang)
    2. Atau mengembalikan True/False dengan logging informatif
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
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status in (200, 201, 302, 303):
                    return True
        except Exception as e:
            print(f"[SHEETS-WEBHOOK] Gagal push real-time ke Google Apps Script: {e}")

    return False


def export_registrations_csv(category_id: Optional[str] = None) -> str:
    """Mengekspor pendaftaran ke string CSV standar."""
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
            "Tersinkron" if r.get("synced_to_sheets") else "Tersimpan Lokal",
        ])

    return output.getvalue()
