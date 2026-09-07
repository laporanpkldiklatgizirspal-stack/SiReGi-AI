"""Pengolahan data: filter, pencarian, rekap, dan analisis sederhana."""

from __future__ import annotations

import pandas as pd


def filter_kolom(df: pd.DataFrame, kolom: str, nilai: list) -> pd.DataFrame:
    """Filter satu kolom terhadap daftar nilai yang dipilih."""
    if not kolom or not nilai:
        return df
    return df[df[kolom].astype(str).isin([str(n) for n in nilai])]


def cari_teks(df: pd.DataFrame, teks: str, kolom_utama=None) -> pd.DataFrame:
    """Pencarian bebas ke semua kolom teks."""
    teks = (teks or "").strip().lower()
    if not teks:
        return df
    kolom_cari = []
    for kol in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[kol]) or pd.api.types.is_numeric_dtype(df[kol]):
            continue
        kolom_cari.append(kol)
    if not kolom_cari:
        kolom_cari = [kolom_utama] if kolom_utama else list(df.columns)
    mask = pd.Series(False, index=df.index)
    for kol in kolom_cari:
        try:
            mask = mask | df[kol].astype(str).str.lower().str.contains(teks, na=False)
        except Exception:  # noqa: BLE001
            continue
    return df[mask]


def rekap_kategori(df: pd.DataFrame, kolom_kategori: str) -> pd.DataFrame:
    """Jumlah baris + persentase per kategori."""
    if not kolom_kategori or kolom_kategori not in df.columns:
        return pd.DataFrame()
    out = (
        df[kolom_kategori]
        .astype(str)
        .replace("", "(kosong)")
        .value_counts()
        .rename("Jumlah")
        .reset_index()
        .rename(columns={"index": kolom_kategori})
    )
    out["Persentase (%)"] = (out["Jumlah"] / out["Jumlah"].sum() * 100).round(2)
    return out


def rekap_numerik(
    df: pd.DataFrame, kolom_kategori: str, kolom_nilai: str, agregasi: str = "sum"
) -> pd.DataFrame:
    """Rekap nilai numerik per kategori (sum/mean/min/max/count)."""
    if not kolom_kategori or not kolom_nilai:
        return pd.DataFrame()
    if kolom_kategori not in df.columns or kolom_nilai not in df.columns:
        return pd.DataFrame()
    df2 = df.copy()
    df2[kolom_kategori] = df2[kolom_kategori].astype(str).replace("", "(kosong)")
    df2[kolom_nilai] = pd.to_numeric(df2[kolom_nilai], errors="coerce")
    out = df2.groupby(kolom_kategori, as_index=False)[kolom_nilai].agg(agregasi)
    out.columns = [kolom_kategori, f"{agregasi.title()} {kolom_nilai}"]
    return out


def siapkan_tren(
    df: pd.DataFrame, kolom_tanggal: str, kolom_nilai: str, agregasi: str = "sum"
) -> pd.DataFrame:
    """Siapkan data tren bulanan.

    Bisa dipakai untuk kolom bertipe tanggal ATAU kolom teks '2025-07'.
    """
    if not kolom_tanggal or kolom_tanggal not in df.columns or not kolom_nilai:
        return pd.DataFrame()
    df2 = df.copy()
    seri = df2[kolom_tanggal]
    if not pd.api.types.is_datetime64_any_dtype(seri):
        seri = pd.to_datetime(seri, errors="coerce", dayfirst=True)
    df2 = df2[pd.notna(seri)].copy()
    df2["_bulan"] = seri.dt.to_period("M").astype(str)
    df2[kolom_nilai] = pd.to_numeric(df2[kolom_nilai], errors="coerce")
    out = df2.groupby("_bulan", as_index=False)[kolom_nilai].agg(agregasi)
    out.columns = ["Bulan", f"{agregasi.title()} {kolom_nilai}"]
    return out


def statistik_ringkas(df: pd.DataFrame, kolom_nilai: str) -> dict:
    """Ringkasan statistik satu kolom angka."""
    if not kolom_nilai or kolom_nilai not in df.columns:
        return {}
    seri = pd.to_numeric(df[kolom_nilai], errors="coerce").dropna()
    if seri.empty:
        return {}
    return {
        "Jumlah": float(seri.sum()),
        "Rata-rata": float(seri.mean()),
        "Min": float(seri.min()),
        "Maks": float(seri.max()),
        "Total Data": int(seri.count()),
    }
