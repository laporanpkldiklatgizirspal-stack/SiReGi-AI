"""Membaca & membersihkan file Excel menjadi DataFrame siap olah."""

from __future__ import annotations

import pandas as pd

EKSTENSI_BENAR = (".xlsx", ".xls", ".xlsm")


def validasi_nama_file(nama_file: str) -> bool:
    """Pastikan file berformat Excel."""
    if not nama_file:
        return False
    return nama_file.lower().endswith(EKSTENSI_BENAR)


def baca_semua_sheet(sumber) -> dict[str, pd.DataFrame]:
    """Membaca SEMUA sheet dari file Excel.

    sumber bisa berupa objek UploadedFile (Streamlit) atau path file.
    """
    try:
        return pd.read_excel(sumber, sheet_name=None)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Tidak bisa membaca file Excel. Pastikan file tidak rusak "
            f"dan benar-benar berformat .xlsx/.xls. Detail: {exc}"
        ) from exc


def bersihkan_df(df: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan DataFrame: nama kolom rapi, buang baris/kolom kosong total."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")                 # baris yang semua kosong
    df = df.loc[:, ~df.columns.duplicated()]  # kolom dobel
    df = df.dropna(axis=1, how="all")         # kolom yang semua kosong
    return df.reset_index(drop=True)


def _coba_jadikan_tanggal(seri: pd.Series) -> pd.Series:
    """Coba ubah kolom menjadi datetime; kalau gagal kembalikan apa adanya."""
    if pd.api.types.is_datetime64_any_dtype(seri):
        return seri
    contoh = seri.dropna().astype(str).head(50)
    if contoh.empty:
        return seri
    try:
        hasil = pd.to_datetime(seri, errors="coerce", dayfirst=True)
        if hasil.notna().mean() >= 0.6:  # minimal 60% terbaca sebagai tanggal
            return hasil
    except Exception:  # noqa: BLE001
        pass
    return seri


def normalisasi_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ubah tipe kolom secara otomatis (tanggal, angka, kategori/teks)."""
    df = bersihkan_df(df)
    for kol in df.columns:
        seri = df[kol]

        # 1) Angka
        if pd.api.types.is_numeric_dtype(seri):
            continue

        # 2) Tanggal (coba dulu, sebelum diperlakukan sebagai teks)
        if seri.dropna().astype(str).str.match(r"^\d{4}[-/]\d{1,2}").mean() >= 0.6:
            df[kol] = _coba_jadikan_tanggal(seri)
            continue
        coba_tgl = _coba_jadikan_tanggal(seri)
        if pd.api.types.is_datetime64_any_dtype(coba_tgl):
            df[kol] = coba_tgl
            continue

        # 3) Teks / kategori
        df[kol] = seri.astype(str).str.strip().replace({"nan": "", "None": "", "<NA>": ""})
    return df


def deteksi_kolom(df: pd.DataFrame) -> dict:
    """Deteksi otomatis: kolom tanggal, angka, dan kategori.

    Hasilnya dipakai sebagai saran default di sidebar; tetap bisa diubah
    manual oleh pengguna dari dropdown aplikasi.
    """
    kolom_tanggal: list[str] = []
    kolom_angka: list[str] = []
    kolom_kategori: list[str] = []

    kata_tanggal = ("tanggal", "tgl", "date", "waktu", "bulan", "tahun", "periode")
    kata_kategori = (
        "kategori", "jenis", "diet", "indikator", "unit", "ruang", "status",
        "kelas", "shift", "petugas", "kegiatan", "nama", "ruangan", "poli",
    )

    for kol in df.columns:
        seri = df[kol]
        rendah = str(kol).lower()

        if pd.api.types.is_datetime64_any_dtype(seri) or any(k in rendah for k in kata_tanggal):
            if pd.api.types.is_datetime64_any_dtype(seri) or seri.dropna().shape[0] > 0:
                kolom_tanggal.append(kol)
        elif pd.api.types.is_numeric_dtype(seri):
            kolom_angka.append(kol)
        elif any(k in rendah for k in kata_kategori):
            kolom_kategori.append(kol)
        else:
            # teks dengan sedikit nilai unik -> kategori
            unik = seri.dropna().nunique()
            if unik > 0 and unik / max(seri.dropna().shape[0], 1) <= 0.5:
                kolom_kategori.append(kol)
            else:
                kolom_kategori.append(kol)  # teks bebas tetap bisa difilter

    return {
        "kolom_tanggal": kolom_tanggal,
        "kolom_angka": kolom_angka,
        "kolom_kategori": kolom_kategori,
        "kolom_semua": list(df.columns),
    }


def info_kosong(df: pd.DataFrame) -> pd.DataFrame:
    """Ringkasan jumlah data kosong per kolom (untuk ditampilkan)."""
    kosong = df.isna().sum()
    kosong = kosong[kosong > 0]
    if kosong.empty:
        return pd.DataFrame({"Kolom": [], "Jumlah Kosong": []})
    return kosong.reset_index().rename(columns={"index": "Kolom", 0: "Jumlah Kosong"})
