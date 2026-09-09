"""
GiziLens — kalkulator nutrisi murni (tanpa UI/database).

Status warna & persen batas harian, estimasi dampak produk ke total harian,
kontributor terbesar, dst. Semua fungsi deterministik -> mudah diuji.
"""

from __future__ import annotations

import config
from utils import fmt_jumlah, salt_gram


def status_persen(persen: float, ambang: dict | None = None) -> str:
    ambang = ambang or config.STATUS_THRESHOLDS
    if persen >= ambang["danger"]:
        return "danger"      # merah
    if persen >= ambang["warning"]:
        return "warning"     # kuning
    return "safe"            # hijau


_BADGE = {
    "safe": ("🟢 HIJAU", "Aman"),
    "warning": ("🟡 KUNING", "Perlu perhatian"),
    "danger": ("🔴 MERAH", "Melebihi batas harian"),
}


def badge(warna: str) -> tuple[str, str]:
    return _BADGE.get(warna, _BADGE["safe"])


def persen_dari(nilai: float, batas: float) -> float:
    return (float(nilai) / float(batas) * 100.0) if batas else 0.0


def ringkas_zat(nilai: float, batas: float, ambang: dict | None = None) -> dict:
    """Satu zat gizi -> dict ringkasan (konsumsi/batas/persen/status/sisa/lebih)."""
    pct = persen_dari(nilai, batas)
    warna = status_persen(persen=pct, ambang=ambang)
    badge_teks, pesan = badge(warna)
    sisa = max(float(batas) - float(nilai), 0.0)
    lebih = max(float(nilai) - float(batas), 0.0)
    return {
        "konsumsi": float(nilai),
        "batas": float(batas),
        "persen": pct,
        "warna": warna,
        "badge": badge_teks,
        "pesan": pesan,
        "sisa": sisa,
        "lebih": lebih,
    }


def ringkas_garam(total_natrium: float, batas_natrium: float,
                  ambang: dict | None = None) -> dict:
    """Ringkasan natrium + estimasi garam (g)."""
    r = ringkas_zat(total_natrium, batas_natrium, ambang)
    r["garam_g"] = salt_gram(total_natrium)
    r["garam_batas_g"] = salt_gram(batas_natrium)
    r["garam_sisa_g"] = max(r["garam_batas_g"] - r["garam_g"], 0.0)
    return r


def total_status(ringkasan: dict[str, dict]) -> str:
    """Warna keseluruhan hari: merah jika ada merah, kuning jika ada kuning."""
    if any(r and r["warna"] == "danger" for r in ringkasan.values()):
        return "danger"
    if any(r and r["warna"] == "warning" for r in ringkasan.values()):
        return "warning"
    return "safe"


# ---------------------------------------------------------------------------
# Dampak prediksi penambahan produk
# ---------------------------------------------------------------------------
def nilai_dikonsumsi(per_sajian: dict, jumlah_sajian: float) -> dict:
    """GGL yang benar-benar dikonsumsi = per sajian x jumlah sajian."""
    return {
        "sugar_g": float(per_sajian.get("gula", 0)) * float(jumlah_sajian),
        "sodium_mg": float(per_sajian.get("natrium", 0)) * float(jumlah_sajian),
        "fat_g": float(per_sajian.get("lemak", 0)) * float(jumlah_sajian),
    }


def dampak_penambahan(total_hari_ini: dict, dikonsumsi: dict,
                      ambang: dict | None = None) -> dict:
    """Prediksi total & status KALAU produk ditambahkan (belum disimpan)."""
    ambang = ambang or config.STATUS_THRESHOLDS
    batas = config.DAILY_LIMITS
    hasil = {}
    # kolom_db -> (kunci_zat, kunci_batas)
    peta = {"sugar_g": ("gula", "sugar_g"),
            "sodium_mg": ("natrium", "sodium_mg"),
            "fat_g": ("lemak", "fat_g")}
    for kolom, (kunci, batas_kunci) in peta.items():
        now = float(total_hari_ini.get(kolom, 0) or 0)
        tambah = float(dikonsumsi.get(kolom, 0) or 0)
        prediksi = now + tambah
        batas_zat = batas[batas_kunci]
        hasil[kunci] = {
            "sekarang": now,
            "tambah": tambah,
            "prediksi": prediksi,
            "batas": batas_zat,
            "persen_sekarang": persen_dari(now, batas_zat),
            "persen_prediksi": persen_dari(prediksi, batas_zat),
            "warna_prediksi": status_persen(persen_dari(prediksi, batas_zat), ambang),
            "lewat": max(prediksi - batas_zat, 0.0),
        }
    return hasil


def kontributor_tertinggi(baris_hari: list, kolom: str):
    """Produk penyumbang terbesar utk satu kolom (sugar_g/sodium_mg/fat_g)."""
    terbaik = None
    for b in baris_hari:
        nilai = float(b[kolom] or 0)
        if terbaik is None or nilai > terbaik["nilai"]:
            terbaik = {"id": b["id"], "nama": b["product_name"] or "Tanpa nama",
                       "nilai": nilai, "waktu": b["time"]}
    return terbaik


def status_overview(ringkasan: dict[str, dict]) -> str:
    badge_teks, pesan = badge(total_status(ringkasan))
    return f"{badge_teks} · {pesan}"
