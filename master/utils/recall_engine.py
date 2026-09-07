"""Mesin hitung ala NutriSurvey: input bahan -> zat gizi -> kebutuhan.

Rumus zat gizi MENGIKUTI file Excel MASTER TKPI + Recall milik Subdep Gizi:
    zat gizi = nilai TKPI (per 100 g BDD) x BB(gram) / BDD
sehingga angka di aplikasi web sama persis dengan angka di Excel mereka.
"""

from __future__ import annotations

import io

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from utils import parser_recall as pr

NAMA_GIZI = pr.NAMA_GIZI
SATUAN = {"Energi": "kkal", "Protein": "g", "Lemak": "g", "KH": "g", "Serat": "g",
          "Ca": "mg", "Fe": "mg", "Na": "mg", "K": "mg", "Vit. C": "mg"}

FAKTOR_AKTIVITAS = {
    "Istirahat di tempat tidur": 1.2,
    "Ringan (kerja kantor, sedikit gerak)": 1.375,
    "Sedang (banyak berdiri/berjalan)": 1.55,
    "Berat (kerja fisik berat)": 1.725,
}


def cari_bahan(tkpi: pd.DataFrame, nama: str) -> pd.Series | None:
    """Cari bahan di database TKPI (case-insensitive, cocok sebagian)."""
    if not nama:
        return None
    cocok = tkpi[
        tkpi["Nama Bahan Makanan"].str.lower() == nama.strip().lower()
    ]
    if cocok.empty:
        cocok = tkpi[
            tkpi["Nama Bahan Makanan"].str.lower().str.contains(nama.strip().lower(), na=False)
        ]
    if cocok.empty:
        return None
    return cocok.iloc[0]


def hitung_item(tkpi: pd.DataFrame, nama_bahan: str, bb: float) -> dict | None:
    """Hitung zat gizi satu bahan seberat bb gram. None bila bahan tak ditemukan."""
    baris = cari_bahan(tkpi, nama_bahan)
    if baris is None:
        return None
    bdd = float(baris["BDD"]) if pd.notna(baris["BDD"]) and float(baris["BDD"]) > 0 else 100.0
    hasil = {}
    for g in NAMA_GIZI:
        nilai = baris[g]
        if pd.isna(nilai):
            hasil[g] = 0.0
        else:
            hasil[g] = round(float(nilai) * float(bb) / bdd, 3)
    return {
        "bahan": str(baris["Nama Bahan Makanan"]),
        "bb": bb,
        "bdd": bdd,
        "zat": hasil,
    }


def kebutuhan_pasien(jk: str, umur: float, bb: float, tb: float, aktivitas: str) -> dict:
    """Estimasi kebutuhan energi (Harris-Benedict) + protein/lemak/KH."""
    if jk == "Laki-laki":
        bmr = 66 + (13.7 * bb) + (5 * tb) - (6.8 * umur)
    else:
        bmr = 655 + (9.6 * bb) + (1.8 * tb) - (4.7 * umur)
    faktor = FAKTOR_AKTIVITAS.get(aktivitas, 1.375)
    tee = max(bmr, 0) * faktor
    return {
        "Energi": tee,
        "Protein": (0.15 * tee) / 4,     # 15% energi dari protein
        "Lemak": (0.25 * tee) / 9,       # 25% dari lemak
        "KH": (0.60 * tee) / 4,          # 60% dari karbohidrat
        "BMR": bmr,
        "faktor": faktor,
    }


# ------------------------------------------------------------------
# Menulis hasil input menjadi file Excel format MASTER TKPI + Recall
# ------------------------------------------------------------------
def _tulis_style_header(ws, baris: int, sampai_kolom: int):
    for j in range(1, sampai_kolom + 1):
        cell = ws.cell(row=baris, column=j)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0E7C66")


def tulis_file_recall(tkpi: pd.DataFrame, identitas: dict, daftar: list[dict]) -> io.BytesIO:
    """Bangun workbook .xlsx dengan 2 sheet seperti file master mereka."""
    wb = Workbook()

    # ---- Sheet 1: REKAP BAHAN MAKANAN (salinan database TKPI) ----
    ws = wb.active
    ws.title = "REKAP BAHAN MAKANAN"
    for r in range(1, 5):
        for c in range(1, 13):
            ws.cell(row=r, column=c)
    ws.cell(row=5, column=1, value="DATABASE TKPI")
    ws.cell(row=6, column=1, value="Nama Bahan Makanan")
    ws.cell(row=6, column=2, value="Zat Gizi")
    ws.cell(row=6, column=12, value="BDD")
    for j, g in enumerate(NAMA_GIZI):
        ws.cell(row=7, column=2 + j, value=g)
    satuan_baris = ["kkl", "g", "g", "g", "g", "mg", "mg", "mg", "mg", "mg"]
    for j, s in enumerate(satuan_baris):
        ws.cell(row=8, column=2 + j, value=s)
    _tulis_style_header(ws, 6, 12)
    _tulis_style_header(ws, 7, 12)
    _tulis_style_header(ws, 8, 12)
    r = 9
    for _, baris in tkpi.iterrows():
        ws.cell(row=r, column=1, value=str(baris["Nama Bahan Makanan"]))
        for j, g in enumerate(NAMA_GIZI):
            v = baris[g]
            ws.cell(row=r, column=2 + j, value=None if pd.isna(v) else float(v))
        bdd = baris["BDD"]
        ws.cell(row=r, column=12, value=None if pd.isna(bdd) else float(bdd))
        r += 1

    # ---- Sheet 2: RECALL ----
    ws2 = wb.create_sheet("RECALL")
    ident_rows = [
        ("Nama", identitas.get("Nama", ""), "NO RM", identitas.get("NO RM", "")),
        ("Usia", identitas.get("Usia", ""), "Diagnosa", identitas.get("Diagnosa", "")),
        ("Jenis Diet", identitas.get("Jenis Diet", ""), "", ""),
        ("Konsistensi", identitas.get("Konsistensi", ""), "", ""),
    ]
    for i, (l1, v1, l2, v2) in enumerate(ident_rows, start=1):
        ws2.cell(row=i, column=1, value=l1)
        ws2.cell(row=i, column=2, value=":")
        ws2.cell(row=i, column=3, value=v1 if str(v1) not in ("nan", "None") else "")
        if l2:
            ws2.cell(row=i, column=4, value=l2)
            ws2.cell(row=i, column=5, value=":")
            ws2.cell(row=i, column=6, value=v2 if str(v2) not in ("nan", "None") else "")

    judul = ["Waktu", "Menu", "Bahan", "BB"] + NAMA_GIZI
    for j, h in enumerate(judul, start=1):
        ws2.cell(row=6, column=j, value=h)
    ws2.cell(row=8, column=4, value="g")
    ws2.cell(row=8, column=5, value="kkl")
    for j in range(6, 14):
        ws2.cell(row=8, column=j, value="mg" if j > 11 else ("g" if j <= 9 else "mg"))
    # perbaiki satuan: E=kkl(5) F..I=g(6-9) J..N=mg(10-14)
    for j, s in zip(range(5, 15), ["kkl", "g", "g", "g", "g", "mg", "mg", "mg", "mg", "mg"]):
        ws2.cell(row=8, column=j, value=s)
    _tulis_style_header(ws2, 6, 14)

    r = 9
    for item in daftar:
        zat = item["zat"]
        baris_tkpi = cari_bahan(tkpi, item["bahan"])
        ws2.cell(row=r, column=1, value=item.get("waktu", "Siang"))
        ws2.cell(row=r, column=2, value=item.get("menu", ""))
        ws2.cell(row=r, column=3, value=item["bahan"])
        ws2.cell(row=r, column=4, value=item["bb"])
        for j, g in enumerate(NAMA_GIZI):
            ws2.cell(row=r, column=5 + j, value=zat.get(g, 0))
        if baris_tkpi is not None:
            ws2.cell(row=r, column=16, value=str(baris_tkpi["Nama Bahan Makanan"]))  # P
            for j, g in enumerate(NAMA_GIZI):
                v = baris_tkpi[g]
                ws2.cell(row=r, column=17 + j, value=None if pd.isna(v) else float(v))  # Q..Z
            ws2.cell(row=r, column=27, value=float(baris_tkpi["BDD"]) if pd.notna(baris_tkpi["BDD"]) else 100.0)  # AA
        r += 1

    for wsx in (ws, ws2):
        wsx.column_dimensions["A"].width = 30
        wsx.column_dimensions["B"].width = 10
        wsx.column_dimensions["C"].width = 16
        wsx.column_dimensions["D"].width = 10

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
