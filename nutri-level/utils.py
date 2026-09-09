"""
GiziLens — util format angka & tanggal Indonesia.
"""

import datetime as _dt

HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def today_iso() -> str:
    return _dt.date.today().isoformat()


def now_time() -> str:
    return _dt.datetime.now().strftime("%H:%M")


def tanggal_id(tgl: _dt.date) -> str:
    """Rabu, 9 September 2026"""
    return f"{HARI_ID[tgl.weekday()]}, {tgl.day} {BULAN_ID[tgl.month - 1]} {tgl.year}"


def fmt_jumlah(v) -> str:
    """4 -> '4'; 18.5 -> '18,5'; 1250 -> '1.250'"""
    if v is None:
        return "—"
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}".replace(",", ".")
    return f"{v:.1f}".replace(".", ",")


def fmt_persen(p) -> str:
    if p is None:
        return "—"
    if abs(p - round(p)) < 1e-9:
        return str(int(round(p)))
    return f"{p:.1f}".replace(".", ",")


def fmt_decimal(v, desimal: int = 1) -> str:
    """0.375 -> '0,4' (tampilan garam)."""
    return f"{v:.{desimal}f}".replace(".", ",")


def salt_gram(natrium_mg: float) -> float:
    """Estimasi garam (g) dari natrium (mg)."""
    from config import SODIUM_TO_SALT_FACTOR
    return natrium_mg * SODIUM_TO_SALT_FACTOR


def parse_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
