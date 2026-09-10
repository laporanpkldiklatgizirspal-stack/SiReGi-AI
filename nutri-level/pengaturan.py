"""
GiziLens — pengaturan aplikasi yang bisa diubah dari dalam aplikasi (tanpa edit kode).

Disimpan di data/pengaturan.json (ikut pindah saat folder aplikasi disalin).
Kalau folder tidak bisa ditulis (mis. server cloud read-only) -> pakai folder temp,
dan aplikasi memberi tahu bahwa pengaturan tidak permanen.

Isi:
  ambang_minuman : batas Nutri-Level per 100 mL (sudah terisi sesuai poster Kemenkes)
  ambang_makanan : batas Nutri-Level per 100 g (diisi sesuai poster/aturan resmi)
  batas_harian   : batas GGL harian (Permenkes 30/2013)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import config
from nutri_level import NUTRI_LEVEL_MINUMAN, NUTRI_LEVEL_MAKANAN

BAWAAN = {
    "ambang_minuman": {k: list(v) for k, v in NUTRI_LEVEL_MINUMAN.items()},
    "ambang_makanan": {k: list(v) for k, v in NUTRI_LEVEL_MAKANAN.items()},
    "batas_harian": dict(config.DAILY_LIMITS),
    "batas_nutri_level_makanan_sumber": "",   # catatan: dari poster/aturan mana angkanya diambil
}

_PAKAI_TEMP = False


def _jalur() -> Path:
    global _PAKAI_TEMP
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    jalur = config.DATA_DIR / "pengaturan.json"
    try:
        with open(jalur, "a"):
            pass
        return jalur
    except OSError:
        _PAKAI_TEMP = True
        jalur = Path(tempfile.gettempdir()) / "gizilens_pengaturan.json"
        return jalur


def lokasi_temp() -> bool:
    return _PAKAI_TEMP


def muat() -> dict:
    """Baca pengaturan; kalau belum ada / rusak -> pakai bawaan."""
    data = json.loads(json.dumps(BAWAAN))     # salinan dalam
    try:
        isi = json.loads(_jalur().read_text(encoding="utf-8"))
    except Exception:
        return data
    for kunci in ("ambang_minuman", "ambang_makanan", "batas_harian"):
        if isinstance(isi.get(kunci), dict):
            for zat, nilai in isi[kunci].items():
                if isinstance(nilai, list) and len(nilai) == 3:
                    data[kunci][zat] = [float(x) for x in nilai]
                elif isinstance(nilai, (int, float)):
                    data[kunci][zat] = float(nilai)
    if isinstance(isi.get("batas_nutri_level_makanan_sumber"), str):
        data["batas_nutri_level_makanan_sumber"] = isi["batas_nutri_level_makanan_sumber"]
    return data


def simpan(data: dict) -> bool:
    try:
        _jalur().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def ambang_aktif(jenis: str) -> dict:
    """Tabel ambang yang dipakai aplikasi untuk jenis produk tertentu.

    Zat yang batas C-nya 0 / kosong dianggap belum diisi (tidak dipakai).
    """
    d = muat()
    tabel = d["ambang_minuman"] if jenis == "minuman" else d["ambang_makanan"]
    bersih = {}
    for k, v in (tabel or {}).items():
        if isinstance(v, list) and len(v) == 3 and float(v[2]) > 0:
            bersih[k] = [float(x) for x in v]
    return bersih
