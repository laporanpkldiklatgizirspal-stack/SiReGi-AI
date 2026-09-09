"""
GiziLens — konfigurasi pusat (batas GGL, warna, ambang, jalur database).
Semua angka yang bisa berubah disimpan di sini agar mudah diperbarui.
"""

from pathlib import Path

# ---------- Identitas ----------
APP_NAME = "GiziLens"
APP_TAGLINE = "Scan Label • Kenali Gizi • Pantau GGL"
ORG = "Sub Departemen Gizi RSPAL dr. Ramelan"
ORG_SINGKAT = "Subdep Gizi RSPAL dr. Ramelan"

# ---------- Batas GGL harian (Permenkes RI No. 30/2013 & WHO) ----------
DAILY_LIMITS = {
    "sugar_g": 50.0,      # gula per hari (gram)
    "sodium_mg": 2000.0,  # natrium per hari (mg)
    "fat_g": 67.0,        # lemak total per hari (gram)
}

# Ambang warna akumulasi harian (configurable)
STATUS_THRESHOLDS = {
    "warning": 50.0,   # >= 50%  -> kuning
    "danger": 100.0,   # >= 100% -> merah
}

# Warna resmi (spec)
COLORS = {
    "safe": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
}

# Konversi natrium -> garam (2.000 mg natrium ≈ 5 g garam)
SODIUM_TO_SALT_FACTOR = 2.5 / 1000.0

# Zat gizi utama yang dipantau (urutan tampilan)
NUTRIENTS = [
    {"key": "gula",    "emoji": "🍬", "label": "GULA",          "unit": "g",  "limit_key": "sugar_g",   "jenis": "Gula"},
    {"key": "natrium", "emoji": "🧂", "label": "GARAM/NATRIUM", "unit": "mg", "limit_key": "sodium_mg", "jenis": "Natrium"},
    {"key": "lemak",   "emoji": "🥑", "label": "LEMAK TOTAL",   "unit": "g",  "limit_key": "fat_g",     "jenis": "Lemak"},
]

# Kolom database (subset yang dijumlahkan)
DB_SUM_COLUMNS = ("sugar_g", "sodium_mg", "fat_g")

# ---------- Jalur database ----------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_FILENAME = "gizilens.db"
