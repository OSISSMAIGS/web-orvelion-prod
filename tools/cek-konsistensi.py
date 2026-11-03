#!/usr/bin/env python3
"""Cek konsistensi nama tab spreadsheet antara situs dan Code.gs.

Nama sheet yang dikirim situs (orvelion/nordelia.py) harus sama dengan
DAFTAR_CABANG_LOMBA di Code.gs — kalau beda, Apps Script akan membuat
tab baru otomatis dan spreadsheet jadi berantakan (tab dobel).

Jalankan dari akar repo:
    python tools/cek-konsistensi.py

Keluar 0 = konsisten; keluar 1 = ada selisih (daftarannya dicetak).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from orvelion.nordelia import KATEGORI_LOMBA, KUOTA_CABANG, _sheet_name  # noqa: E402


def sheet_dari_code_gs() -> set[str]:
    sumber = (AKAR / "Code.gs").read_text(encoding="utf-8")
    blok = re.search(r"DAFTAR_CABANG_LOMBA\s*=\s*\[(.*?)\];", sumber, re.S)
    if not blok:
        raise SystemExit("Code.gs: blok DAFTAR_CABANG_LOMBA tidak ditemukan.")
    return set(re.findall(r'name:\s*"([^"]+)"', blok.group(1)))


def main() -> int:
    sheet_situs: set[str] = set()
    for kat in KATEGORI_LOMBA:
        for lomba in kat["lomba"]:
            subs = lomba.get("subs")
            if not subs:
                sheet_situs.add(_sheet_name(lomba, None, lomba["nama"]))
            else:
                # Semua kombinasi (lomba, sub) — termasuk yang cabang_id-nya
                # sama (debat LDBI/NSDC) karena tab tujuannya beda.
                for sub in subs:
                    sheet_situs.add(_sheet_name(lomba, sub, ""))
    sheet_gs = sheet_dari_code_gs()

    masalah = 0

    hanya_situs = sorted(sheet_situs - sheet_gs)
    if hanya_situs:
        masalah += 1
        print("[X] Dikirim situs tapi TIDAK ada di Code.gs (tab dobel bakal terbuat):")
        for nama in hanya_situs:
            print(f"    - {nama}")

    hanya_gs = sorted(sheet_gs - sheet_situs)
    if hanya_gs:
        masalah += 1
        print("[!] Ada di Code.gs tapi TIDAK bisa dipilih di situs (tab kosong):")
        for nama in hanya_gs:
            print(f"    - {nama}")

    kuota_tak_dikenal = sorted(set(KUOTA_CABANG) - sheet_situs)
    if kuota_tak_dikenal:
        masalah += 1
        print("[X] KUOTA_CABANG menunjuk sheet yang tidak dikenal situs:")
        for nama in kuota_tak_dikenal:
            print(f"    - {nama}")

    kuota_tak_selaras = sorted(set(KUOTA_CABANG) - sheet_gs)
    if kuota_tak_selaras:
        masalah += 1
        print("[X] KUOTA_CABANG menunjuk sheet yang tidak ada di Code.gs:")
        for nama in kuota_tak_selaras:
            print(f"    - {nama}")

    if masalah == 0:
        print(f"[OK] Konsisten: {len(sheet_situs)} tab selaras antara situs & Code.gs "
              f"({len(KUOTA_CABANG)} di antaranya berkuota).")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
