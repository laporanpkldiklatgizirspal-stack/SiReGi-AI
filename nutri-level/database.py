"""
GiziLens — database SQLite (data konsumsi permanen, bukan session_state).

Tabel daily_consumption menyimpan tiap produk yang BENAR-BENAR dikonsumsi.
Semua query memakai parameterized query (aman dari SQL injection).
"""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import tempfile
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Lokasi database: coba data/ di folder aplikasi; kalau tidak writable
# (mis. di Streamlit Cloud folder repo read-only) -> pakai folder temp.
# ---------------------------------------------------------------------------
DB_PATH: Path = config.DATA_DIR / config.DB_FILENAME
_LOKASI_CADANGAN = False


def _pilih_jalur_db() -> Path:
    global _LOKASI_CADANGAN
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    jalur = config.DATA_DIR / config.DB_FILENAME
    try:
        with open(jalur, "a"):  # uji tulis
            pass
        _LOKASI_CADANGAN = False
        return jalur
    except OSError:
        _LOKASI_CADANGAN = True
        tmp = Path(tempfile.gettempdir()) / config.DB_FILENAME
        try:
            with open(tmp, "a"):
                pass
        except OSError:
            tmp = Path(tempfile.gettempdir()) / "gizilens_cadangan.db"
        return tmp


def lokasi_db_cadangan() -> bool:
    """True kalau DB jatuh ke folder temp (data bisa hilang saat server berhenti)."""
    return _LOKASI_CADANGAN


_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_consumption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    product_name TEXT,
    serving_size TEXT,
    consumed_servings REAL,
    sugar_g REAL DEFAULT 0,
    sodium_mg REAL DEFAULT 0,
    salt_g REAL DEFAULT 0,
    fat_g REAL DEFAULT 0,
    saturated_fat_g REAL DEFAULT 0,
    nutri_level TEXT
);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_consumption(date);
"""


def _migrasi(kon: sqlite3.Connection) -> None:
    """Tambah kolom baru ke database lama (tanpa menghapus data yang sudah ada)."""
    kolom = {baris[1] for baris in kon.execute("PRAGMA table_info(daily_consumption)")}
    if "saturated_fat_g" not in kolom:
        kon.execute("ALTER TABLE daily_consumption ADD COLUMN saturated_fat_g REAL DEFAULT 0")
    if "nutri_level" not in kolom:
        kon.execute("ALTER TABLE daily_consumption ADD COLUMN nutri_level TEXT")


def init_database(jalur_db: Path | None = None) -> Path:
    """Buat tabel kalau belum ada. Return jalur db yang dipakai."""
    global DB_PATH
    if jalur_db is not None:
        DB_PATH = jalur_db
    else:
        DB_PATH = _pilih_jalur_db()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as kon:
        kon.executescript(_SCHEMA)
        _migrasi(kon)
    return DB_PATH


def _koneksi() -> sqlite3.Connection:
    kon = sqlite3.connect(DB_PATH)
    kon.row_factory = sqlite3.Row
    return kon


# ---------------------------------------------------------------------------
# Tambah
# ---------------------------------------------------------------------------
def add_consumption(date: str, time: str, product_name: str, serving_size: str,
                    consumed_servings: float, sugar_g: float = 0.0,
                    sodium_mg: float = 0.0, fat_g: float = 0.0,
                    saturated_fat_g: float = 0.0, nutri_level: str | None = None) -> int:
    from utils import salt_gram
    salt = salt_gram(float(sodium_mg or 0))
    with _koneksi() as kon:
        cur = kon.execute(
            """INSERT INTO daily_consumption
               (date, time, product_name, serving_size, consumed_servings,
                sugar_g, sodium_mg, salt_g, fat_g, saturated_fat_g, nutri_level)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (date, time, product_name or "", serving_size or "",
             float(consumed_servings), float(sugar_g or 0),
             float(sodium_mg or 0), salt, float(fat_g or 0),
             float(saturated_fat_g or 0), nutri_level),
        )
        return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Baca
# ---------------------------------------------------------------------------
def get_daily_consumption(date: str) -> list[sqlite3.Row]:
    with _koneksi() as kon:
        return kon.execute(
            "SELECT * FROM daily_consumption WHERE date = ? ORDER BY time, id",
            (date,),
        ).fetchall()


def get_daily_totals(date: str) -> dict:
    with _koneksi() as kon:
        row = kon.execute(
            """SELECT COALESCE(SUM(sugar_g),0)  AS sugar_g,
                      COALESCE(SUM(sodium_mg),0) AS sodium_mg,
                      COALESCE(SUM(salt_g),0)    AS salt_g,
                      COALESCE(SUM(fat_g),0)     AS fat_g,
                      COUNT(*) AS n_produk
               FROM daily_consumption WHERE date = ?""",
            (date,),
        ).fetchone()
    return dict(row)


def get_consumption_between(tgl_awal: str, tgl_akhir: str) -> list[sqlite3.Row]:
    with _koneksi() as kon:
        return kon.execute(
            "SELECT * FROM daily_consumption WHERE date BETWEEN ? AND ? ORDER BY date, time, id",
            (tgl_awal, tgl_akhir),
        ).fetchall()


def get_all_consumption() -> list[sqlite3.Row]:
    with _koneksi() as kon:
        return kon.execute(
            "SELECT * FROM daily_consumption ORDER BY date DESC, time DESC, id DESC"
        ).fetchall()


# ---------------------------------------------------------------------------
# Ubah & hapus
# ---------------------------------------------------------------------------
def update_consumption(record_id: int, consumed_servings: float | None = None,
                       sugar_g: float | None = None, sodium_mg: float | None = None,
                       fat_g: float | None = None, product_name: str | None = None,
                       serving_size: str | None = None,
                       saturated_fat_g: float | None = None,
                       nutri_level: str | None = None) -> None:
    from utils import salt_gram
    set_ = []
    nilai = []
    if consumed_servings is not None:
        set_.append("consumed_servings = ?")
        nilai.append(float(consumed_servings))
    if sugar_g is not None:
        set_.append("sugar_g = ?")
        nilai.append(float(sugar_g))
    if sodium_mg is not None:
        set_.append("sodium_mg = ?")
        set_.append("salt_g = ?")
        nilai.extend([float(sodium_mg), salt_gram(float(sodium_mg))])
    if fat_g is not None:
        set_.append("fat_g = ?")
        nilai.append(float(fat_g))
    if product_name is not None:
        set_.append("product_name = ?")
        nilai.append(product_name)
    if serving_size is not None:
        set_.append("serving_size = ?")
        nilai.append(serving_size)
    if saturated_fat_g is not None:
        set_.append("saturated_fat_g = ?")
        nilai.append(float(saturated_fat_g))
    if nutri_level is not None:
        set_.append("nutri_level = ?")
        nilai.append(nutri_level)
    if not set_:
        return
    nilai.append(int(record_id))
    with _koneksi() as kon:
        kon.execute(f"UPDATE daily_consumption SET {', '.join(set_)} WHERE id = ?", nilai)


def delete_consumption(record_id: int) -> None:
    with _koneksi() as kon:
        kon.execute("DELETE FROM daily_consumption WHERE id = ?", (int(record_id),))


# ---------------------------------------------------------------------------
# Ringkasan 7 hari
# ---------------------------------------------------------------------------
def get_weekly_summary(akhir: _dt.date | None = None) -> list[dict]:
    """Total per hari utk 7 hari terakhir (termasuk hari akhir)."""
    akhir = akhir or _dt.date.today()
    awal = akhir - _dt.timedelta(days=6)
    baris = get_consumption_between(awal.isoformat(), akhir.isoformat())
    per_hari: dict[str, dict] = {}
    for b in baris:
        d = b["date"]
        h = per_hari.setdefault(d, {"sugar_g": 0.0, "sodium_mg": 0.0, "fat_g": 0.0})
        h["sugar_g"] += b["sugar_g"] or 0
        h["sodium_mg"] += b["sodium_mg"] or 0
        h["fat_g"] += b["fat_g"] or 0
    hasil = []
    for i in range(7):
        tgl = awal + _dt.timedelta(days=i)
        iso = tgl.isoformat()
        h = per_hari.get(iso, {"sugar_g": 0.0, "sodium_mg": 0.0, "fat_g": 0.0})
        h["date"] = iso
        hasil.append(h)
    return hasil
