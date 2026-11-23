"""
Skrip Diagnostik Koneksi MySQL cPanel JagoanHosting
Jalankan di terminal cPanel atau lokal:
    python test_jagoan_mysql.py
"""

import os
import sys

# Tambahkan direktori root ke sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orvelion.sheets_service import get_config, load_env_file

print("=" * 60)
print("🔍 MEMERIKSA KONEKSI DATABASE MYSQL JAGOAN HOSTING")
print("=" * 60)

# 1. Cek File .env
load_env_file()
host = get_config("DB_HOST", "localhost").strip()
port = int(get_config("DB_PORT", "3306"))
user = get_config("DB_USER", "").strip()
password = get_config("DB_PASSWORD", "").strip()
db_name = get_config("DB_NAME", "").strip()

print(f"📄 Konfigurasi terdeteksi dari .env:")
print(f"   • DB_HOST     : {host}")
print(f"   • DB_PORT     : {port}")
print(f"   • DB_USER     : {user or '(KOSONG)'}")
print(f"   • DB_PASSWORD : {'*' * len(password) if password else '(KOSONG)'}")
print(f"   • DB_NAME     : {db_name or '(KOSONG)'}")
print("-" * 60)

if not user or not db_name:
    print("❌ ERROR: DB_USER atau DB_NAME masih kosong di file .env!")
    print("   Silakan isi di .env cPanel Anda:")
    print("   DB_HOST=localhost")
    print("   DB_PORT=3306")
    print("   DB_USER=osissma1_admin-eduvella")
    print("   DB_PASSWORD=admin-eduvella")
    print("   DB_NAME=osissma1_voting-eduvella")
    sys.exit(1)

# 2. Cek Driver PyMySQL
try:
    import pymysql
    print(f"✅ Driver pymysql terinstall: versi {pymysql.__version__}")
except ImportError:
    print("❌ Driver 'pymysql' BELUM terinstall di virtual environment!")
    print("   Solusi: Jalankan perintah berikut di terminal cPanel:")
    print("   pip install pymysql cryptography")
    sys.exit(1)

# 3. Cek Driver Cryptography (wajib untuk MySQL 8 / caching_sha2_password)
try:
    import cryptography
    print(f"✅ Driver cryptography terinstall: versi {cryptography.__version__}")
except ImportError:
    print("⚠️ Driver 'cryptography' belum terinstall (disarankan untuk MySQL 8).")
    print("   Bila gagal auth, jalankan: pip install cryptography")

print("-" * 60)
print(f"🔄 Mencoba menyambungkan ke MySQL database '{db_name}'...")

# 4. Tes Koneksi
attempts = [
    {"name": f"TCP {host}:{port}", "params": {"host": host, "port": port}},
]
if host.lower() in ("localhost", "127.0.0.1"):
    attempts.append({"name": "TCP 127.0.0.1:3306", "params": {"host": "127.0.0.1", "port": port}})
    for sock in ["/var/lib/mysql/mysql.sock", "/tmp/mysql.sock", "/var/run/mysqld/mysqld.sock"]:
        if os.path.exists(sock):
            attempts.append({"name": f"UNIX Socket ({sock})", "params": {"unix_socket": sock}})

connected = False
for att in attempts:
    print(f"   Mencoba jalur: {att['name']} ... ", end="", flush=True)
    try:
        conn_params = {
            "user": user,
            "password": password,
            "database": db_name,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": 5,
        }
        conn_params.update(att["params"])
        conn = pymysql.connect(**conn_params)
        print("BERHASIL! 🎉")

        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS ver, DATABASE() AS cur_db, USER() AS cur_usr")
            info = cur.fetchone()
            print(f"   • Versi MySQL Server : {info.get('ver')}")
            print(f"   • Database Aktif     : {info.get('cur_db')}")
            print(f"   • User Terotentikasi : {info.get('cur_usr')}")

            # Cek atau buat tabel jika belum ada
            from orvelion.voting_db import voting_storage
            print("   • Status Inisialisasi: Tabel 'voting_ballots' dan 'voting_coupons' siap!")

            cur.execute("SELECT COUNT(*) AS total FROM voting_ballots")
            cnt = cur.fetchone()
            print(f"   • Total Suara Tersimpan di MySQL: {cnt.get('total', 0)} suara")

        conn.close()
        connected = True
        break
    except Exception as e:
        print(f"GAGAL ({e})")

print("=" * 60)
if connected:
    print("✅ STATUS: Database MySQL JagoanHosting BERFUNGSI 100%!")
    print("   Sistem voting website akan langsung menggunakan database ini.")
else:
    print("❌ STATUS: Gagal terhubung ke MySQL JagoanHosting.")
    print("\n💡 Panduan Perbaikan di cPanel JagoanHosting:")
    print("1. Buka cPanel -> menu 'MySQL Databases'.")
    print(f"2. Pastikan database '{db_name}' sudah ada.")
    print(f"3. Pastikan user '{user}' sudah dibuat dengan password yang benar.")
    print("4. PENTING: Pada bagian 'Add User to Database':")
    print(f"   Pilih User '{user}' dan Database '{db_name}' -> Klik 'Add'")
    print("   Centang 'ALL PRIVILEGES' -> Klik 'Make Changes'.")
    print("5. Jalankan kembali: python test_jagoan_mysql.py")
print("=" * 60)
