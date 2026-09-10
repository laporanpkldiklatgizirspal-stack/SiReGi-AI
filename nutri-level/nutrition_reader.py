"""
GiziLens — pembaca label (kamera -> AI/OCR -> nilai GGL).

Membungkus nutri_core (mesin OCR rapidocr + AI Vision Gemini).
read_label() -> dict hasil scan dengan kunci:
  nama_produk, takaran_saji, sajian_per_kemasan, gula, natrium, lemak,
  protein, karbohidrat, energi, _sumber, _baris, _gemini_error
"""

from __future__ import annotations

import nutri_core as _core

# Variasi penulisan yang dikenali (dipakai utk dokumentasi & edukasi)
ALIAS_LABEL = {
    "gula": ["Gula", "Total Gula", "Sugars", "Total Sugars"],
    "natrium": ["Natrium", "Garam (Natrium)", "Sodium", "Salt"],
    "lemak": ["Lemak Total", "Total Lemak", "Total Fat", "Fat"],
}


def read_label(byte_gambar: bytes, gemini_key: str | None = None,
               gambar_tambahan: list | None = None) -> dict:
    """Baca label dari 1..N foto (PNG/JPEG). Foto tambahan dipakai untuk melengkapi angka."""
    return _core.read_nutrition_label(byte_gambar, gemini_key=gemini_key,
                                      gambar_tambahan=gambar_tambahan)


NAMA_FIELD = {
    "nama_produk": "nama produk",
    "takaran_saji": "takaran saji",
    "gula": "gula",
    "natrium": "natrium",
    "lemak": "lemak total",
    "lemak_jenuh": "lemak jenuh",
}


def ringkas_auto(hasil: dict) -> dict:
    """Ringkasan: berapa item yang terisi otomatis & mana yang masih perlu diisi."""
    kurang = list((hasil or {}).get("_kurang") or [])
    if not kurang and "_kurang" not in (hasil or {}):
        kurang = [k for k, _ in NAMA_FIELD.items() if (hasil or {}).get(k) in (None, "")]
    total = len(NAMA_FIELD)
    terisi = total - len(kurang)
    return {
        "terisi": terisi,
        "total": total,
        "kurang": kurang,
        "label_terisi": ", ".join(NAMA_FIELD[k] for k in NAMA_FIELD if k not in kurang),
        "label_kurang": ", ".join(NAMA_FIELD.get(k, k) for k in kurang),
    }


def kunci_gemini_dari_secrets():
    """Baca GEMINI_API_KEY dari st.secrets kalau ada (aman kalau tidak ada)."""
    try:
        import streamlit as st
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


def nama_default_produk(hasil: dict) -> str:
    nama = (hasil or {}).get("nama_produk") or ""
    return str(nama).strip() if isinstance(nama, str) else ""
