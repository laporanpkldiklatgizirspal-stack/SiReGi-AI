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


def read_label(byte_gambar: bytes, gemini_key: str | None = None) -> dict:
    """Baca label dari byte gambar (PNG/JPEG)."""
    return _core.read_nutrition_label(byte_gambar, gemini_key=gemini_key)


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
