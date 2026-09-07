"""Parser khusus file Excel 'MASTER TKPI + Recall' (format Subdep Gizi).

Struktur file:
  Sheet 'REKAP BAHAN MAKANAN' = database TKPI:
      baris judul, lalu header: Nama Bahan Makanan | Energi..Vit. C (per 100 g) | BDD
  Sheet 'RECALL' = catatan asupan 1 pasien:
      blok identitas (Nama, Usia, Jenis Diet, Konsistensi, NO RM, Diagnosa)
      lalu tabel: Waktu | Menu | Bahan | BB(g) | Energi..Vit. C (hasil hitung)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

NAMA_GIZI = ["Energi", "Protein", "Lemak", "KH", "Serat", "Ca", "Fe", "Na", "K", "Vit. C"]
SHEET_TKPI = "REKAP BAHAN MAKANAN"
SHEET_RECALL = "RECALL"


# ------------------------------------------------------------------
# Database TKPI
# ------------------------------------------------------------------
def baca_tkpi(sumber) -> pd.DataFrame:
    """Membaca sheet database TKPI -> DataFrame rapi.

    Kolom hasil: Nama Bahan Makanan, Energi, Protein, Lemak, KH, Serat,
    Ca, Fe, Na, K, Vit. C, BDD
    """
    df = pd.read_excel(sumber, sheet_name=SHEET_TKPI, header=None)
    # Cari baris header 'Nama Bahan Makanan'
    idx_header = None
    for i in range(min(12, len(df))):
        if str(df.iloc[i, 0]).strip() == "Nama Bahan Makanan":
            idx_header = i
            break
    if idx_header is None:
        raise ValueError("Sheet 'REKAP BAHAN MAKANAN' tidak ditemukan / format tidak dikenal.")

    data = df.iloc[idx_header + 1 :].copy()          # baris unit + data
    unit = data.iloc[0]                               # baris satuan (kkl, g, mg)
    data = data.iloc[1:]                              # mulai baris data
    data = data[data[0].notna() & data[0].astype(str).str.strip().ne("")]  # buang baris kosong

    kolom = {0: "Nama Bahan Makanan"}
    for j, nama in enumerate(NAMA_GIZI):
        kolom[j + 1] = nama
    kolom[11] = "BDD"
    out = data.rename(columns=kolom)[list(kolom.values())].copy()
    for k in NAMA_GIZI + ["BDD"]:
        out[k] = pd.to_numeric(out[k], errors="coerce")
    out["Nama Bahan Makanan"] = out["Nama Bahan Makanan"].astype(str).str.strip()
    return out.reset_index(drop=True)


# ------------------------------------------------------------------
# Sheet RECALL (asupan pasien)
# ------------------------------------------------------------------
def _cari_nilai_identitas(df: pd.DataFrame, kunci: str):
    """Cari label (mis. 'Nama') di blok identitas; nilai ada 2 kolom setelahnya.

    Pola baris: [Label][:][nilai]  [Label2][:][nilai2]
    """
    for i in range(min(8, len(df))):
        for j in range(df.shape[1] - 2):
            sel = df.iloc[i, j]
            if sel is None or pd.isna(sel):
                continue
            if str(sel).strip().lower() == kunci.lower():
                v = df.iloc[i, j + 2]
                if v is None or pd.isna(v):
                    return ""
                teks = str(v).strip()
                return "" if teks in ("", ":", "nan", "None") else teks
    return ""


def baca_recall(sumber) -> dict:
    """Membaca sheet RECALL -> {'identitas': dict, 'data': DataFrame, 'masalah': list}."""
    df = pd.read_excel(sumber, sheet_name=SHEET_RECALL, header=None)

    identitas = {
        "Nama": _cari_nilai_identitas(df, "Nama"),
        "NO RM": _cari_nilai_identitas(df, "NO RM"),
        "Usia": _cari_nilai_identitas(df, "Usia"),
        "Diagnosa": _cari_nilai_identitas(df, "Diagnosa"),
        "Jenis Diet": _cari_nilai_identitas(df, "Jenis Diet"),
        "Konsistensi": _cari_nilai_identitas(df, "Konsistensi"),
    }

    # Cari baris header tabel (A == 'Waktu' dan C == 'Bahan')
    idx_header = None
    for i in range(len(df)):
        if str(df.iloc[i, 0]).strip() == "Waktu" and str(df.iloc[i, 2]).strip() == "Bahan":
            idx_header = i
            break
    if idx_header is None:
        raise ValueError("Tabel recall (Waktu/Menu/Bahan) tidak ditemukan di sheet RECALL.")

    # Nama kolom zat gizi diambil dari baris header (E..N) -> NAMA_GIZI urut
    raw = df.iloc[idx_header + 2 :].copy()  # lewati baris satuan
    raw = raw[raw[2].notna() & raw[2].astype(str).str.strip().ne("")]

    kolom = {0: "Waktu", 1: "Menu", 2: "Bahan", 3: "BB"}
    for j, nama in enumerate(NAMA_GIZI):
        kolom[j + 4] = nama
    kolom[15] = "NamaTKPI"   # kolom P: nama bahan yang cocok di TKPI
    kolom[26] = "BDD_TKPI"   # kolom AA: BDD dari TKPI

    tabel = raw.rename(columns=kolom)
    pakai = [k for k in kolom.values() if k in tabel.columns]
    tabel = tabel[pakai].copy()
    tabel["Waktu"] = tabel["Waktu"].replace("", pd.NA).ffill()   # isi dari baris atas
    tabel["Menu"] = tabel["Menu"].replace("", pd.NA).ffill()
    tabel["Waktu"] = tabel["Waktu"].fillna("(tanpa waktu)")
    tabel["Menu"] = tabel["Menu"].fillna("(tanpa menu)")

    for k in NAMA_GIZI:
        tabel[k] = pd.to_numeric(tabel[k], errors="coerce")
    tabel["BB"] = pd.to_numeric(tabel["BB"], errors="coerce")

    masalah = []
    tidak_ada = tabel[tabel[NAMA_GIZI].isna().all(axis=1) & tabel["Bahan"].notna()]
    if not tidak_ada.empty:
        daftar = ", ".join(tidak_ada["Bahan"].astype(str).unique()[:10])
        masalah.append(f"{len(tidak_ada)} baris bahan tidak ditemukan di database TKPI: {daftar}")

    return {"identitas": identitas, "data": tabel.reset_index(drop=True), "masalah": masalah}


# ------------------------------------------------------------------
# Rekap & analisis recall
# ------------------------------------------------------------------
def total_asupan(items: pd.DataFrame) -> pd.Series:
    """Total zat gizi dari semua bahan (dalam satuan sesuai kolom)."""
    return items[NAMA_GIZI].sum(numeric_only=True)


def rekap_per_waktu(items: pd.DataFrame) -> pd.DataFrame:
    """Total zat gizi per waktu makan."""
    if items.empty:
        return pd.DataFrame()
    return items.groupby("Waktu", as_index=False)[NAMA_GIZI].sum(numeric_only=True)


def rekap_per_menu(items: pd.DataFrame) -> pd.DataFrame:
    """Total zat gizi per menu."""
    if items.empty:
        return pd.DataFrame()
    return items.groupby(["Waktu", "Menu"], as_index=False)[NAMA_GIZI].sum(numeric_only=True)


def bahan_tidak_ditemukan(items: pd.DataFrame) -> pd.DataFrame:
    """Baris bahan yang tidak punya nilai zat gizi (tidak cocok TKPI)."""
    if items.empty:
        return pd.DataFrame()
    return items[items[NAMA_GIZI].isna().all(axis=1)].copy()


def format_angka(v, desimal: int = 1) -> str:
    """Angka -> teks rapi (ribuan pakai titik)."""
    try:
        if pd.isna(v):
            return "-"
        return f"{float(v):,.{desimal}f}".replace(",", " ")
    except Exception:  # noqa: BLE001
        return "-"
