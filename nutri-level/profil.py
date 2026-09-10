"""
GiziLens — profil pengguna (sederhana) yang disimpan di perangkat/aplikasi.

Isinya sengaja minimal supaya gampang diisi: nama, umur, jenis kelamin, tinggi/berat,
kondisi medis yang perlu diperhatikan, dan tujuan. Disimpan di data/profil.json
(kalau folder aplikasi read-only -> folder temp, dan aplikasi memberi tahu).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import config

BAWAAN = {
    "nama": "",
    "umur": 25,
    "jenis_kelamin": "Perempuan",
    "tinggi_cm": 160.0,
    "berat_kg": 55.0,
    "kondisi": [],          # daftar kunci kondisi, mis. ["diabetes", "hipertensi"]
    "tujuan": "menjaga",    # menurunkan | menjaga | menambah
}

_PAKAI_TEMP = False


def _jalur() -> Path:
    global _PAKAI_TEMP
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    jalur = config.DATA_DIR / "profil.json"
    try:
        with open(jalur, "a"):
            pass
        return jalur
    except OSError:
        _PAKAI_TEMP = True
        return Path(tempfile.gettempdir()) / "gizilens_profil.json"


def lokasi_temp() -> bool:
    return _PAKAI_TEMP


def muat() -> dict:
    data = json.loads(json.dumps(BAWAAN))
    try:
        isi = json.loads(_jalur().read_text(encoding="utf-8"))
    except Exception:
        return data
    for k in BAWAAN:
        if k in isi:
            data[k] = isi[k]
    if not isinstance(data.get("kondisi"), list):
        data["kondisi"] = []
    return data


def simpan(data: dict) -> bool:
    bersih = dict(BAWAAN)
    bersih.update({k: v for k, v in (data or {}).items() if k in BAWAAN})
    try:
        _jalur().write_text(json.dumps(bersih, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def ada_profil() -> bool:
    """True kalau pengguna sudah pernah mengisi (minimal ada nama atau kondisi)."""
    d = muat()
    return bool(str(d.get("nama", "")).strip()) or bool(d.get("kondisi"))


def ringkas(data: dict | None = None) -> str:
    d = data or muat()
    bagian = []
    if str(d.get("nama", "")).strip():
        bagian.append(str(d["nama"]).strip())
    bagian.append(f"{d.get('umur', '-')} thn")
    if d.get("kondisi"):
        from kesesuaian import nama_kondisi
        bagian.append(", ".join(nama_kondisi(k) for k in d["kondisi"]))
    return " · ".join(bagian)


def imt(data: dict | None = None) -> float | None:
    """Indeks Massa Tubuh (kg/m²) kalau tinggi & berat terisi."""
    d = data or muat()
    try:
        t = float(d.get("tinggi_cm") or 0) / 100.0
        b = float(d.get("berat_kg") or 0)
        if t > 0.5 and b > 0:
            return round(b / (t * t), 1)
    except (TypeError, ValueError):
        pass
    return None
