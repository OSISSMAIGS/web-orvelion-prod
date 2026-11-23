"""
Database & Kupon Service untuk Event Eduvella (Voting Apresiasi Guru 2026)
Mendukung Login Akun Google Sekolah (@students.ignatiusglobal.sch.id) & Kupon
Mendukung MySQL (cPanel JagoanHosting) dengan Fallback Otomatis ke SQLite Lokal
SMA Ignatius Global School (IGS) Palembang - OSIS Kabinet Orvelion
"""

import os
import re
import secrets
import sqlite3
import string
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from orvelion.sheets_service import get_config, load_env_file
from orvelion.voting_data import NOMINATIONS

load_env_file()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_SQLITE_PATH = os.path.join(BASE_DIR, "voting_eduvella.db")

SCHOOL_DOMAIN = get_config("SCHOOL_GOOGLE_DOMAIN", "students.ignatiusglobal.sch.id").strip().lower()

_lock = threading.RLock()


def is_valid_school_email(email: str) -> bool:
    """Memeriksa apakah email merupakan akun Google resmi siswa IGS."""
    if not email or "@" not in email:
        return False
    domain = email.split("@")[1].strip().lower()
    return domain == SCHOOL_DOMAIN


_last_mysql_fail_time = 0.0


def _get_mysql_connection():
    """Mengkoneksikan ke fitur database MySQL resmi cPanel JagoanHosting.
    Mendukung koneksi otomatis via TCP (host:port, 127.0.0.1) dan UNIX socket cPanel.
    """
    global _last_mysql_fail_time

    user = get_config("DB_USER", "")
    db_name = get_config("DB_NAME", "")
    if not user or not db_name:
        return None

    try:
        import pymysql
    except ImportError:
        print("[CRITICAL] Pustaka 'pymysql' belum terinstall di Python cPanel. Jalankan: pip install pymysql cryptography")
        return None

    host = get_config("DB_HOST", "localhost").strip()
    port = int(get_config("DB_PORT", "3306"))
    password = get_config("DB_PASSWORD", "")

    # Jalur koneksi yang dicoba berurutan untuk menjamin tembus di cPanel JagoanHosting:
    attempts = [
        {"host": host, "port": port},
    ]
    # Jika host adalah localhost/127.0.0.1, tambahkan fallback eksplisit TCP 127.0.0.1 & UNIX sockets
    if host.lower() in ("localhost", "127.0.0.1"):
        if host != "127.0.0.1":
            attempts.append({"host": "127.0.0.1", "port": port})
        for sock in ["/var/lib/mysql/mysql.sock", "/tmp/mysql.sock", "/var/run/mysqld/mysqld.sock"]:
            if os.path.exists(sock):
                attempts.append({"unix_socket": sock})

    last_err = None
    for opt in attempts:
        try:
            params = {
                "user": user,
                "password": password,
                "database": db_name,
                "charset": "utf8mb4",
                "cursorclass": pymysql.cursors.DictCursor,
                "connect_timeout": 4,
                "autocommit": False,
            }
            params.update(opt)
            conn = pymysql.connect(**params)
            return conn
        except Exception as e:
            last_err = e

    if last_err:
        print(f"[MySQL JagoanHosting Error] Gagal konek ke database '{db_name}' dengan user '{user}': {last_err}")
    return None


class VotingStorage:
    def __init__(self):
        self._init_db()

    def _get_db(self):
        """Mengembalikan koneksi aktif database (Prioritas Mutlak: MySQL cPanel JagoanHosting)."""
        mysql_conn = _get_mysql_connection()
        if mysql_conn:
            return "mysql", mysql_conn

        # Jika konfigurasi MySQL sudah diset di .env
        user = get_config("DB_USER", "")
        db_name = get_config("DB_NAME", "")
        if user and db_name:
            print(f"[VOTING-DB] PERINGATAN: Konfigurasi MySQL ({user} @ {db_name}) aktif tapi gagal tersambung. Memeriksa status...")

        # Fallback cadangan hanya jika MySQL tidak aktif sama sekali
        sqlite_conn = sqlite3.connect(LOCAL_SQLITE_PATH, timeout=10)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_conn.execute("PRAGMA busy_timeout=5000")
        sqlite_conn.execute("PRAGMA synchronous=NORMAL")
        return "sqlite", sqlite_conn

    def _init_db(self):
        """Membuat tabel yang dibutuhkan jika belum ada dan memigrasikan kolom baru."""
        with _lock:
            driver, conn = self._get_db()
            try:
                if driver == "mysql":
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS voting_coupons (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                token VARCHAR(64) NOT NULL UNIQUE,
                                is_used TINYINT(1) DEFAULT 0,
                                used_at DATETIME NULL,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """)
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS voting_ballots (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                coupon_token VARCHAR(64) DEFAULT '',
                                voter_email VARCHAR(191) NULL UNIQUE,
                                voter_name VARCHAR(191) NULL,
                                auth_provider VARCHAR(50) DEFAULT 'google',
                                nomination_1 VARCHAR(191) NOT NULL,
                                nomination_2 VARCHAR(191) NOT NULL,
                                nomination_3 VARCHAR(191) NOT NULL,
                                nomination_4 VARCHAR(191) NOT NULL,
                                nomination_5 VARCHAR(191) NOT NULL,
                                nomination_6 VARCHAR(191) NOT NULL,
                                nomination_7 VARCHAR(191) NOT NULL,
                                nomination_8 VARCHAR(191) NOT NULL,
                                nomination_9 VARCHAR(191) NOT NULL,
                                nomination_10 VARCHAR(191) NOT NULL,
                                ip_address VARCHAR(64) DEFAULT '',
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """)
                    conn.commit()
                else:
                    cur = conn.cursor()
                    cur.execute("PRAGMA journal_mode=WAL")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS voting_coupons (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            token TEXT NOT NULL UNIQUE,
                            is_used INTEGER DEFAULT 0,
                            used_at TEXT NULL,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS voting_ballots (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            coupon_token TEXT DEFAULT '',
                            voter_email TEXT NULL UNIQUE,
                            voter_name TEXT NULL,
                            auth_provider TEXT DEFAULT 'google',
                            nomination_1 TEXT NOT NULL,
                            nomination_2 TEXT NOT NULL,
                            nomination_3 TEXT NOT NULL,
                            nomination_4 TEXT NOT NULL,
                            nomination_5 TEXT NOT NULL,
                            nomination_6 TEXT NOT NULL,
                            nomination_7 TEXT NOT NULL,
                            nomination_8 TEXT NOT NULL,
                            nomination_9 TEXT NOT NULL,
                            nomination_10 TEXT NOT NULL,
                            ip_address TEXT DEFAULT '',
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    conn.commit()

                # Migrasikan kolom jika tabel sudah ada dari versi sebelumnya
                self._migrate_ballots_schema(driver, conn)
            except Exception as e:
                print(f"[VOTING-DB] Init error: {e}")
            finally:
                conn.close()

            # Pastikan selalu ada kupon starter jika kosong
            self._ensure_seed_coupons()

    def _migrate_ballots_schema(self, driver, conn):
        """Menambahkan kolom voter_email, voter_name, voter_nis, auth_provider, device_fingerprint bila belum ada."""
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute("SHOW COLUMNS FROM voting_ballots LIKE 'voter_email'")
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_email VARCHAR(191) NULL AFTER coupon_token")
                    cur.execute("SHOW COLUMNS FROM voting_ballots LIKE 'voter_name'")
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_name VARCHAR(191) NULL AFTER voter_email")
                    cur.execute("SHOW COLUMNS FROM voting_ballots LIKE 'voter_nis'")
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_nis VARCHAR(64) NULL AFTER voter_name")
                    cur.execute("SHOW COLUMNS FROM voting_ballots LIKE 'auth_provider'")
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE voting_ballots ADD COLUMN auth_provider VARCHAR(50) DEFAULT 'google' AFTER voter_nis")
                    cur.execute("SHOW COLUMNS FROM voting_ballots LIKE 'device_fingerprint'")
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE voting_ballots ADD COLUMN device_fingerprint VARCHAR(128) NULL AFTER auth_provider")
                    cur.execute("SHOW COLUMNS FROM voting_ballots LIKE 'voter_normalized_name'")
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_normalized_name VARCHAR(191) NULL AFTER voter_name")
                        try:
                            cur.execute("CREATE UNIQUE INDEX idx_ballots_norm_name ON voting_ballots(voter_normalized_name)")
                        except Exception:
                            pass
                conn.commit()
            else:
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(voting_ballots)")
                existing = [r[1] for r in cur.fetchall()]
                if "voter_email" not in existing:
                    cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_email TEXT NULL")
                if "voter_name" not in existing:
                    cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_name TEXT NULL")
                if "voter_normalized_name" not in existing:
                    cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_normalized_name TEXT NULL")
                if "voter_nis" not in existing:
                    cur.execute("ALTER TABLE voting_ballots ADD COLUMN voter_nis TEXT NULL")
                if "auth_provider" not in existing:
                    cur.execute("ALTER TABLE voting_ballots ADD COLUMN auth_provider TEXT DEFAULT 'google'")
                if "device_fingerprint" not in existing:
                    cur.execute("ALTER TABLE voting_ballots ADD COLUMN device_fingerprint TEXT NULL")
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ballots_norm_name ON voting_ballots(voter_normalized_name) WHERE voter_normalized_name IS NOT NULL AND voter_normalized_name != ''")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_ballots_device_fp ON voting_ballots(device_fingerprint)")
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ballots_nis ON voting_ballots(voter_nis) WHERE voter_nis IS NOT NULL AND voter_nis != ''")
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ballots_email ON voting_ballots(voter_email) WHERE voter_email IS NOT NULL AND voter_email != ''")
                conn.commit()
        except Exception as e:
            print(f"[VOTING-DB] Migration note: {e}")

    def _ensure_seed_coupons(self):
        """Membuat kupon starter otomatis jika tabel kupon masih kosong."""
        count = self.get_total_coupons()
        if count == 0:
            self.generate_coupons(count=100, prefix="IGS")

    def get_total_coupons(self) -> int:
        driver, conn = self._get_db()
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS total FROM voting_coupons")
                    row = cur.fetchone()
                    return row["total"] if row else 0
            else:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM voting_coupons")
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0
        finally:
            conn.close()

    def generate_coupons(self, count: int = 50, prefix: str = "IGS") -> List[str]:
        chars = string.ascii_uppercase + string.digits
        safe_chars = [c for c in chars if c not in ("O", "0", "I", "1")]

        tokens = []
        with _lock:
            driver, conn = self._get_db()
            try:
                cur = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for _ in range(count):
                    rand = "".join(secrets.choice(safe_chars) for _ in range(6))
                    token = f"{prefix}-{rand}"
                    try:
                        if driver == "mysql":
                            cur.execute(
                                "INSERT INTO voting_coupons (token, is_used, created_at) VALUES (%s, 0, %s)",
                                (token, now_str),
                            )
                        else:
                            cur.execute(
                                "INSERT INTO voting_coupons (token, is_used, created_at) VALUES (?, 0, ?)",
                                (token, now_str),
                            )
                        tokens.append(token)
                    except Exception:
                        pass
                conn.commit()
            finally:
                conn.close()
        return tokens

    # =========================================================================
    # GOOGLE ACCOUNT VOTING METHODS (1 Akun Google Sekolah = 1x Vote)
    # =========================================================================
    def check_email_voted(self, raw_email: str) -> Tuple[bool, Optional[str]]:
        """
        Memeriksa apakah akun Google sekolah ini sudah pernah memberikan suara.
        Return: (has_voted, vote_timestamp)
        """
        email = (raw_email or "").strip().lower()
        if not email:
            return False, None

        driver, conn = self._get_db()
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT created_at FROM voting_ballots WHERE LOWER(voter_email) = %s LIMIT 1",
                        (email,),
                    )
                    row = cur.fetchone()
                    if row:
                        return True, str(row["created_at"])
                    return False, None
            else:
                cur = conn.cursor()
                cur.execute(
                    "SELECT created_at FROM voting_ballots WHERE LOWER(voter_email) = ? LIMIT 1",
                    (email,),
                )
                row = cur.fetchone()
                if row:
                    return True, str(row[0])
                return False, None
        except Exception as e:
            print(f"[VOTING-DB] Error check_email_voted: {e}")
            return False, None
        finally:
            conn.close()

    @staticmethod
    def normalize_name(raw_name: str) -> str:
        """Normalisasi nama: huruf kecil dan buang spasi serta tanda baca non-alfanumerik."""
        if not raw_name:
            return ""
        return re.sub(r"[^a-z0-9]", "", raw_name.lower())

    def check_name_voted(self, raw_name: str) -> Tuple[bool, Optional[str]]:
        """Memeriksa apakah nama pemilih sudah pernah digunakan untuk voting."""
        name = " ".join((raw_name or "").strip().split())
        if not name or len(name) < 2:
            return False, None
        norm_name = self.normalize_name(name)
        driver, conn = self._get_db()
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT voter_name, created_at FROM voting_ballots 
                        WHERE voter_normalized_name = %s 
                           OR LOWER(REPLACE(voter_name, ' ', '')) = %s
                           OR LOWER(TRIM(voter_name)) = LOWER(%s)
                        LIMIT 1
                        """,
                        (norm_name, norm_name, name),
                    )
                    row = cur.fetchone()
                    if row:
                        return True, str(row.get("created_at"))
                    return False, None
            else:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT voter_name, created_at FROM voting_ballots 
                    WHERE voter_normalized_name = ? 
                       OR LOWER(REPLACE(voter_name, ' ', '')) = ?
                       OR LOWER(TRIM(voter_name)) = LOWER(?)
                    LIMIT 1
                    """,
                    (norm_name, norm_name, name),
                )
                row = cur.fetchone()
                if row:
                    return True, str(row[1])
                return False, None
        except Exception as e:
            print(f"[VOTING-DB] Error check_name_voted: {e}")
            return False, None
        finally:
            conn.close()

    def check_device_fp_voted(self, device_fp: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Memeriksa apakah fingerprint perangkat ini sudah pernah dipakai mengirim suara."""
        fp = (device_fp or "").strip()
        if not fp or fp in ("FP-FALLBACK", ""):
            return False, None, None
        driver, conn = self._get_db()
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT voter_name, created_at FROM voting_ballots WHERE device_fingerprint = %s LIMIT 1",
                        (fp,),
                    )
                    row = cur.fetchone()
                    if row:
                        return True, row.get("voter_name"), str(row.get("created_at"))
                    return False, None, None
            else:
                cur = conn.cursor()
                cur.execute(
                    "SELECT voter_name, created_at FROM voting_ballots WHERE device_fingerprint = ? LIMIT 1",
                    (fp,),
                )
                row = cur.fetchone()
                if row:
                    return True, row[0], str(row[1])
                return False, None, None
        except Exception as e:
            print(f"[VOTING-DB] Error check_device_fp_voted: {e}")
            return False, None, None
        finally:
            conn.close()

    def submit_vote_by_name(
        self,
        raw_name: str,
        nominations: Dict[str, str],
        ip_address: str = "",
        device_fp: str = "",
    ) -> Tuple[bool, str]:
        """
        Sistem Utama Sederhana: Siswa cukup mengisi nama lengkap untuk voting.
        Menjamin 1 nama hanya boleh voting 1 kali dan tepat 10 nominasi terisi.
        """
        name = " ".join((raw_name or "").strip().split())
        if not name or len(name) < 2:
            return False, "Silakan masukkan nama lengkap Anda untuk memberikan suara."

        # Validasi nama minimal mengandung huruf
        if not any(c.isalpha() for c in name):
            return False, "Mohon masukkan nama siswa yang sah (mengandung huruf)."

        norm_name = self.normalize_name(name)

        # Validasi tepat seluruh 10 nominasi terisi
        expected_keys = [nom["id"] for nom in NOMINATIONS]
        nom_values = []
        for nom in NOMINATIONS:
            key = nom["id"]
            val = (nominations.get(key) or "").strip()
            if not val:
                return False, f"Pilihan guru untuk kategori '{nom['title']}' belum dipilih. Seluruh 10 nominasi wajib diisi lengkap."
            nom_values.append(val)

        if len(nom_values) != 10:
            return False, "Seluruh 10 nominasi wajib diisi lengkap (tidak boleh kurang atau lebih)."

        with _lock:
            # 1. Cek Nama Pemilih (1 nama = 1 kali)
            already_voted, voted_at = self.check_name_voted(name)
            if already_voted:
                return False, f"Nama '{name}' sudah pernah digunakan untuk voting pada {voted_at}. Setiap siswa hanya berhak memilih 1 kali."

            # 2. Cek Perangkat / Device Fingerprint (1 perangkat = 1 kali)
            if device_fp and device_fp != "FP-FALLBACK":
                fp_voted, prev_voter, _ = self.check_device_fp_voted(device_fp)
                if fp_voted:
                    return False, f"Perangkat atau browser ini sudah pernah digunakan untuk voting (tercatat atas nama {prev_voter or 'pemilih sebelumnya'}). Setiap pemilih hanya boleh mengirim 1 kali."

            driver, conn = self._get_db()
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                token_placeholder = f"VOTE-{secrets.token_hex(4).upper()}"

                if driver == "mysql":
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO voting_ballots (
                                coupon_token, voter_name, voter_normalized_name, auth_provider, device_fingerprint,
                                nomination_1, nomination_2, nomination_3, nomination_4,
                                nomination_5, nomination_6, nomination_7, nomination_8,
                                nomination_9, nomination_10, ip_address, created_at
                            ) VALUES (%s, %s, %s, 'name', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (token_placeholder, name, norm_name, device_fp, *nom_values, ip_address, now_str),
                        )
                    conn.commit()
                else:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO voting_ballots (
                            coupon_token, voter_name, voter_normalized_name, auth_provider, device_fingerprint,
                            nomination_1, nomination_2, nomination_3, nomination_4,
                            nomination_5, nomination_6, nomination_7, nomination_8,
                            nomination_9, nomination_10, ip_address, created_at
                        ) VALUES (?, ?, ?, 'name', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (token_placeholder, name, norm_name, device_fp, *nom_values, ip_address, now_str),
                    )
                    conn.commit()

                return True, f"Suara Anda atas nama {name} telah sukses tersimpan! Terima kasih atas partisipasi Anda."
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                err_str = str(e).lower()
                if "unique" in err_str or "duplicate" in err_str:
                    return False, f"Nama '{name}' sudah tercatat pernah memberikan suara. Setiap siswa hanya berhak memilih 1 kali."
                return False, f"Gagal menyimpan suara: {e}"
            finally:
                conn.close()

    def submit_vote_with_google(
        self,
        raw_email: str,
        raw_name: str,
        nominations: Dict[str, str],
        ip_address: str = "",
        device_fp: str = "",
    ) -> Tuple[bool, str]:
        """
        Merekam suara pemilih berdasarkan Akun Google Sekolah resmi (@students.ignatiusglobal.sch.id).
        Menjamin 1 Akun Google hanya bisa vote 1 kali secara aman.
        """
        email = (raw_email or "").strip().lower()
        name = (raw_name or "").strip()

        if not email:
            return False, "Akun Google belum terautentikasi."

        if not is_valid_school_email(email):
            return False, f"Maaf, hanya akun Google sekolah resmi dengan domain @{SCHOOL_DOMAIN} yang berhak melakukan voting."

        # Validasi 10 nominasi terisi
        expected_keys = [nom["id"] for nom in NOMINATIONS]
        nom_values = []
        for nom in NOMINATIONS:
            key = nom["id"]
            val = nominations.get(key, "").strip()
            if not val:
                return False, f"Pilihan guru untuk kategori '{nom['title']}' belum dipilih."
            nom_values.append(val)

        with _lock:
            # Periksa kembali apakah email sudah pernah voting
            already_voted, voted_at = self.check_email_voted(email)
            if already_voted:
                return False, f"Akun Google ini ({email}) sudah pernah digunakan untuk voting pada {voted_at}. Setiap akun hanya berhak memilih 1 kali."

            driver, conn = self._get_db()
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                token_placeholder = f"GOOGLE-{secrets.token_hex(4).upper()}"

                if driver == "mysql":
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO voting_ballots (
                                coupon_token, voter_email, voter_name, auth_provider, device_fingerprint,
                                nomination_1, nomination_2, nomination_3, nomination_4,
                                nomination_5, nomination_6, nomination_7, nomination_8,
                                nomination_9, nomination_10, ip_address, created_at
                            ) VALUES (%s, %s, %s, 'google', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (token_placeholder, email, name, device_fp, *nom_values, ip_address, now_str),
                        )
                    conn.commit()
                else:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO voting_ballots (
                            coupon_token, voter_email, voter_name, auth_provider, device_fingerprint,
                            nomination_1, nomination_2, nomination_3, nomination_4,
                            nomination_5, nomination_6, nomination_7, nomination_8,
                            nomination_9, nomination_10, ip_address, created_at
                        ) VALUES (?, ?, ?, 'google', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (token_placeholder, email, name, device_fp, *nom_values, ip_address, now_str),
                    )
                    conn.commit()

                display_name = name or email
                return True, f"Suara Anda atas nama {display_name} telah sukses tersimpan! Terima kasih atas partisipasi Anda dalam Hari Guru."
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                # Cek jika duplicate entry error
                if "UNIQUE" in str(e).upper() or "DUPLICATE" in str(e).upper():
                    return False, f"Akun Google ({email}) sudah pernah memberikan suara sebelumnya."
                return False, f"Gagal menyimpan suara: {e}"
            finally:
                conn.close()

    def check_nis_voted(self, raw_nis: str) -> Tuple[bool, Optional[str]]:
        """Memeriksa apakah NIS tertentu sudah pernah digunakan untuk voting."""
        nis = (raw_nis or "").strip()
        if not nis:
            return False, None
        driver, conn = self._get_db()
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute("SELECT created_at FROM voting_ballots WHERE voter_nis = %s LIMIT 1", (nis,))
                    row = cur.fetchone()
                    if row:
                        return True, str(row.get("created_at"))
                    return False, None
            else:
                cur = conn.cursor()
                cur.execute("SELECT created_at FROM voting_ballots WHERE voter_nis = ? LIMIT 1", (nis,))
                row = cur.fetchone()
                if row:
                    return True, str(row[0])
                return False, None
        except Exception as e:
            print(f"[VOTING-DB] Error check_nis_voted: {e}")
            return False, None
        finally:
            conn.close()

    def submit_vote_with_nis(
        self,
        raw_nis: str,
        raw_name: str,
        raw_class: str,
        nominations: Dict[str, str],
        ip_address: str = "",
        device_fp: str = "",
    ) -> Tuple[bool, str]:
        """
        Sistem alternatif: Merekam suara pemilih berdasarkan Nomor Induk Siswa (NIS).
        Menjamin 1 NIS hanya bisa vote 1 kali.
        """
        nis = (raw_nis or "").strip()
        name = (raw_name or "").strip()
        class_name = (raw_class or "").strip()

        if not nis:
            return False, "Nomor Induk Siswa (NIS) tidak boleh kosong."
        if not name:
            return False, "Nama lengkap siswa tidak boleh kosong."

        expected_keys = [nom["id"] for nom in NOMINATIONS]
        nom_values = []
        for nom in NOMINATIONS:
            key = nom["id"]
            val = nominations.get(key, "").strip()
            if not val:
                return False, f"Pilihan guru untuk kategori '{nom['title']}' belum dipilih."
            nom_values.append(val)

        with _lock:
            already_voted, voted_at = self.check_nis_voted(nis)
            if already_voted:
                return False, f"NIS {nis} atas nama {name} sudah pernah digunakan untuk voting pada {voted_at}. Setiap siswa hanya berhak memilih 1 kali."

            driver, conn = self._get_db()
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                token_placeholder = f"NIS-{nis}"
                display_name = f"{name} ({class_name})" if class_name else name

                if driver == "mysql":
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO voting_ballots (
                                coupon_token, voter_email, voter_name, voter_nis, auth_provider, device_fingerprint,
                                nomination_1, nomination_2, nomination_3, nomination_4,
                                nomination_5, nomination_6, nomination_7, nomination_8,
                                nomination_9, nomination_10, ip_address, created_at
                            ) VALUES (%s, %s, %s, %s, 'nis', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (token_placeholder, f"{nis}@students.ignatiusglobal.sch.id", display_name, nis, device_fp, *nom_values, ip_address, now_str),
                        )
                    conn.commit()
                else:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO voting_ballots (
                            coupon_token, voter_email, voter_name, voter_nis, auth_provider, device_fingerprint,
                            nomination_1, nomination_2, nomination_3, nomination_4,
                            nomination_5, nomination_6, nomination_7, nomination_8,
                            nomination_9, nomination_10, ip_address, created_at
                        ) VALUES (?, ?, ?, ?, 'nis', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (token_placeholder, f"{nis}@students.ignatiusglobal.sch.id", display_name, nis, device_fp, *nom_values, ip_address, now_str),
                    )
                    conn.commit()

                return True, f"Suara Anda atas nama {name} (NIS: {nis}) telah sukses tersimpan! Terima kasih atas partisipasi Anda."
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                if "UNIQUE" in str(e).upper() or "DUPLICATE" in str(e).upper():
                    return False, f"NIS ({nis}) sudah pernah memberikan suara sebelumnya."
                return False, f"Gagal menyimpan suara: {e}"
            finally:
                conn.close()

    def reset_ballots(self) -> Tuple[bool, str]:
        """
        Menghapus seluruh surat suara testing dan mereset status kupon
        sehingga database kembali bersih untuk live public posting.
        """
        with _lock:
            driver, conn = self._get_db()
            try:
                if driver == "mysql":
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM voting_ballots")
                        cur.execute("UPDATE voting_coupons SET is_used = 0, used_at = NULL")
                    conn.commit()
                else:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM voting_ballots")
                    cur.execute("UPDATE voting_coupons SET is_used = 0, used_at = NULL")
                    conn.commit()
                return True, "Data suara testing berhasil dibersihkan! Sistem siap diposting."
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return False, f"Gagal membersihkan data suara: {e}"
            finally:
                conn.close()

    # =========================================================================
    # KUPON VOTING METHODS (Sebagai opsi tambahan / cadangan)
    # =========================================================================
    def check_coupon(self, raw_token: str) -> Tuple[bool, str, str]:
        if not raw_token:
            return False, "invalid", "Kode kupon wajib diisi."

        token = raw_token.strip().upper()
        driver, conn = self._get_db()
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute("SELECT token, is_used, used_at FROM voting_coupons WHERE token = %s", (token,))
                    row = cur.fetchone()
            else:
                cur = conn.cursor()
                cur.execute("SELECT token, is_used, used_at FROM voting_coupons WHERE token = ?", (token,))
                row = cur.fetchone()

            if not row:
                return False, "invalid", "Kupon tidak ditemukan. Pastikan kode kupon benar."

            is_used = bool(row["is_used"] if driver == "mysql" else row[1])
            if is_used:
                return False, "used", "Kupon ini sudah pernah digunakan sebelumnya (1 Kupon = 1x Vote)."

            return True, "valid", "Kupon valid! Anda dapat memberikan suara."
        except Exception as e:
            return False, "error", f"Gangguan verifikasi kupon: {e}"
        finally:
            conn.close()

    def submit_vote(
        self,
        raw_token: str,
        nominations: Dict[str, str],
        ip_address: str = "",
    ) -> Tuple[bool, str]:
        token = (raw_token or "").strip().upper()
        if not token:
            return False, "Kode kupon tidak boleh kosong."

        expected_keys = [nom["id"] for nom in NOMINATIONS]
        nom_values = []
        for nom in NOMINATIONS:
            key = nom["id"]
            val = nominations.get(key, "").strip()
            if not val:
                return False, f"Pilihan guru untuk kategori '{nom['title']}' belum dipilih."
            nom_values.append(val)

        with _lock:
            driver, conn = self._get_db()
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if driver == "mysql":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, is_used FROM voting_coupons WHERE token = %s FOR UPDATE",
                            (token,),
                        )
                        coupon_row = cur.fetchone()
                        if not coupon_row:
                            return False, "Kupon voting tidak ditemukan."
                        if coupon_row["is_used"]:
                            return False, "Maaf, kupon ini sudah pernah digunakan sebelumnya."

                        cur.execute(
                            """
                            INSERT INTO voting_ballots (
                                coupon_token, nomination_1, nomination_2, nomination_3,
                                nomination_4, nomination_5, nomination_6, nomination_7,
                                nomination_8, nomination_9, nomination_10, ip_address, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (token, *nom_values, ip_address, now_str),
                        )
                        cur.execute(
                            "UPDATE voting_coupons SET is_used = 1, used_at = %s WHERE token = %s",
                            (now_str, token),
                        )
                    conn.commit()
                else:
                    cur = conn.cursor()
                    cur.execute("SELECT id, is_used FROM voting_coupons WHERE token = ?", (token,))
                    coupon_row = cur.fetchone()
                    if not coupon_row:
                        return False, "Kupon voting tidak ditemukan."
                    if coupon_row[1]:
                        return False, "Maaf, kupon ini sudah pernah digunakan sebelumnya."

                    cur.execute(
                        """
                        INSERT INTO voting_ballots (
                            coupon_token, nomination_1, nomination_2, nomination_3,
                            nomination_4, nomination_5, nomination_6, nomination_7,
                            nomination_8, nomination_9, nomination_10, ip_address, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (token, *nom_values, ip_address, now_str),
                    )
                    cur.execute(
                        "UPDATE voting_coupons SET is_used = 1, used_at = ? WHERE token = ?",
                        (now_str, token),
                    )
                    conn.commit()

                return True, "Suara Anda berhasil direkam! Terima kasih atas partisipasi Anda."
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return False, f"Gagal menyimpan voting: {e}"
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        driver, conn = self._get_db()
        try:
            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS total FROM voting_coupons")
                    total_coupons = cur.fetchone()["total"]
                    cur.execute("SELECT COUNT(*) AS used FROM voting_coupons WHERE is_used = 1")
                    used_coupons = cur.fetchone()["used"]
                    cur.execute("SELECT COUNT(*) AS ballots FROM voting_ballots")
                    total_ballots = cur.fetchone()["ballots"]
            else:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM voting_coupons")
                total_coupons = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM voting_coupons WHERE is_used = 1")
                used_coupons = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM voting_ballots")
                total_ballots = cur.fetchone()[0]

            return {
                "driver": driver,
                "school_domain": SCHOOL_DOMAIN,
                "total_coupons": total_coupons,
                "used_coupons": used_coupons,
                "remaining_coupons": max(0, total_coupons - used_coupons),
                "total_ballots": total_ballots,
            }
        except Exception:
            return {"driver": driver, "total_coupons": 0, "used_coupons": 0, "total_ballots": 0}
        finally:
            conn.close()

    def get_voting_results(self) -> Dict[str, Any]:
        """
        Mengambil rekapitulasi lengkap hasil perolehan suara untuk seluruh
        10 nominasi Eduvella 2026 secara real-time dari database.
        Menghasilkan ranking, persentase, serta data format untuk Chart.js.
        """
        driver, conn = self._get_db()
        try:
            total_ballots = 0
            total_students_voted = 0

            if driver == "mysql":
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS total FROM voting_ballots")
                    row = cur.fetchone()
                    total_ballots = row["total"] if row and row.get("total") else 0
                    cur.execute(
                        "SELECT COUNT(DISTINCT voter_email) AS total_students FROM voting_ballots WHERE voter_email IS NOT NULL AND voter_email != ''"
                    )
                    row_s = cur.fetchone()
                    total_students_voted = row_s["total_students"] if row_s and row_s.get("total_students") else 0
            else:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM voting_ballots")
                row = cur.fetchone()
                total_ballots = row[0] if row else 0
                cur.execute(
                    "SELECT COUNT(DISTINCT voter_email) FROM voting_ballots WHERE voter_email IS NOT NULL AND voter_email != ''"
                )
                row_s = cur.fetchone()
                total_students_voted = row_s[0] if row_s else 0

            if total_students_voted == 0 and total_ballots > 0:
                total_students_voted = total_ballots

            categories_results = []

            for nom in NOMINATIONS:
                col_name = f"nomination_{nom['number']}"
                teacher_tallies = []
                category_total = 0

                query = f"""
                    SELECT {col_name} AS teacher_name, COUNT(*) AS vote_count
                    FROM voting_ballots
                    WHERE {col_name} IS NOT NULL AND {col_name} != ''
                    GROUP BY {col_name}
                    ORDER BY vote_count DESC, teacher_name ASC
                """

                if driver == "mysql":
                    with conn.cursor() as cur:
                        cur.execute(query)
                        rows = cur.fetchall()
                        for r in rows:
                            cnt = int(r["vote_count"])
                            teacher_tallies.append({
                                "name": r["teacher_name"],
                                "count": cnt,
                            })
                            category_total += cnt
                else:
                    cur = conn.cursor()
                    cur.execute(query)
                    rows = cur.fetchall()
                    for r in rows:
                        cnt = int(r[1])
                        teacher_tallies.append({
                            "name": r[0],
                            "count": cnt,
                        })
                        category_total += cnt

                # Hitung persentase dan ranking
                ranked_results = []
                for idx, item in enumerate(teacher_tallies, start=1):
                    pct = round((item["count"] / category_total * 100), 1) if category_total > 0 else 0.0
                    ranked_results.append({
                        "rank": idx,
                        "name": item["name"],
                        "count": item["count"],
                        "percentage": pct,
                    })

                winner = ranked_results[0] if ranked_results else None
                top3 = ranked_results[:3]

                # Ambil hingga 8 besar kandidat untuk Chart.js visualisasi agar tetap bersih & elegan
                top_for_chart = ranked_results[:8]
                chart_labels = [c["name"] for c in top_for_chart]
                chart_data = [c["count"] for c in top_for_chart]

                categories_results.append({
                    "id": nom["id"],
                    "number": nom["number"],
                    "title": nom["title"],
                    "subtitle": nom.get("subtitle", ""),
                    "description": nom.get("description", ""),
                    "icon": nom.get("icon", "🏆"),
                    "accent": nom.get("accent", "#F5D061"),
                    "badge": nom.get("badge", ""),
                    "total_votes": category_total,
                    "ranked_results": ranked_results,
                    "winner": winner,
                    "top3": top3,
                    "chart_labels": chart_labels,
                    "chart_data": chart_data,
                })

            now = datetime.now()
            return {
                "total_ballots": total_ballots,
                "total_students_voted": total_students_voted,
                "driver": driver,
                "last_updated": now.strftime("%d %b %Y, %H:%M:%S WIB"),
                "categories": categories_results,
            }
        except Exception as e:
            print(f"[VOTING-DB] Error getting voting results: {e}")
            return {
                "total_ballots": 0,
                "total_students_voted": 0,
                "driver": driver if "driver" in locals() else "unknown",
                "last_updated": datetime.now().strftime("%d %b %Y, %H:%M:%S WIB"),
                "categories": [],
                "error": str(e),
            }
        finally:
            if "conn" in locals() and conn:
                conn.close()


voting_storage = VotingStorage()
