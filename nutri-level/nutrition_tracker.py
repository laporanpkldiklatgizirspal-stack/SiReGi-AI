"""
GiziLens — tracker: jembatan database + kalkulator utk kebutuhan UI harian.
"""

from __future__ import annotations

import datetime as _dt

import config
import database as db
from nutrition_calculator import (dampak_penambahan, kontributor_tertinggi,
                                  nilai_dikonsumsi, ringkas_garam, ringkas_zat,
                                  total_status)


def today() -> str:
    return _dt.date.today().isoformat()


def tambah_catatan(nama_produk, takaran_saji, jumlah_sajian, per_sajian: dict,
                   tanggal: str | None = None, jam: str | None = None) -> int:
    from utils import now_time
    dikonsumsi = nilai_dikonsumsi(per_sajian, jumlah_sajian)
    return db.add_consumption(
        date=tanggal or today(),
        time=jam or now_time(),
        product_name=nama_produk,
        serving_size=takaran_saji,
        consumed_servings=float(jumlah_sajian),
        sugar_g=dikonsumsi["sugar_g"],
        sodium_mg=dikonsumsi["sodium_mg"],
        fat_g=dikonsumsi["fat_g"],
    )


def ringkasan_tanggal(tanggal: str | None = None) -> dict:
    """Ringkasan lengkap satu tanggal utk dashboard."""
    tanggal = tanggal or today()
    total = db.get_daily_totals(tanggal)
    baris = db.get_daily_consumption(tanggal)
    batas = config.DAILY_LIMITS
    ringkas = {
        "gula": ringkas_zat(total["sugar_g"], batas["sugar_g"]),
        "natrium": ringkas_garam(total["sodium_mg"], batas["sodium_mg"]),
        "lemak": ringkas_zat(total["fat_g"], batas["fat_g"]),
    }
    return {
        "tanggal": tanggal,
        "total": total,
        "baris": baris,
        "ringkasan": ringkas,
        "status_keseluruhan": total_status(ringkas),
    }


def dampak_hari_ini(per_sajian: dict, jumlah_sajian: float,
                    tanggal: str | None = None) -> dict:
    total = db.get_daily_totals(tanggal or today())
    dikonsumsi = nilai_dikonsumsi(per_sajian, jumlah_sajian)
    return dampak_penambahan(total, dikonsumsi)


def kontributor_hari_ini(tanggal: str | None = None) -> dict:
    baris = db.get_daily_consumption(tanggal or today())
    return {
        "gula": kontributor_tertinggi(baris, "sugar_g"),
        "natrium": kontributor_tertinggi(baris, "sodium_mg"),
        "lemak": kontributor_tertinggi(baris, "fat_g"),
    }


def ringkasan_7_hari(akhir: _dt.date | None = None) -> dict:
    """Data utk grafik + jumlah hari melebihi batas tiap zat."""
    minggu = db.get_weekly_summary(akhir)
    batas = config.DAILY_LIMITS
    out = {"hari": [], "lewat": {"sugar_g": 0, "sodium_mg": 0, "fat_g": 0}}
    for h in minggu:
        tgl = _dt.date.fromisoformat(h["date"])
        out["hari"].append({
            "tanggal": h["date"],
            "label": f"{tgl.day}/{tgl.month}",
            "hari_nama": ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"][tgl.weekday()],
            "sugar_g": h["sugar_g"],
            "sodium_mg": h["sodium_mg"],
            "fat_g": h["fat_g"],
            "sugar_persen": h["sugar_g"] / batas["sugar_g"] * 100,
            "sodium_persen": h["sodium_mg"] / batas["sodium_mg"] * 100,
            "fat_persen": h["fat_g"] / batas["fat_g"] * 100,
        })
    for h in out["hari"]:
        if h["sugar_persen"] >= 100:
            out["lewat"]["sugar_g"] += 1
        if h["sodium_persen"] >= 100:
            out["lewat"]["sodium_mg"] += 1
        if h["fat_persen"] >= 100:
            out["lewat"]["fat_g"] += 1
    return out
