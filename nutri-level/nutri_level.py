"""
GiziLens — mesin NUTRI-LEVEL (label depan kemasan, Kemenkes).

Dasar hukum: Peraturan/Keputusan Kemenkes RI No. HK.01.07/MENKES/301/2026 (Nutri-Level).
Penilaian memakai kandungan **per 100 mL** untuk minuman dan **per 100 g** untuk makanan.
Huruf akhir produk = level TERBURUK di antara gula, garam (natrium), dan lemak jenuh.

Ambang minuman di bawah ini diambil dari poster resmi Kemenkes (terverifikasi).
Ambang makanan BELUM diisi karena poster versi per 100 g belum ada di tangan kami —
isi lewat ⚙️ Pengaturan di aplikasi (atau tempel angkanya di NUTRI_LEVEL_MAKANAN).
Kalau kosong, aplikasi akan menampilkan catatan bahwa ambang makanan belum tersedia
(tidak menebak-nebak angka).

Modul ini murni hitungan (tanpa UI/database) supaya gampang diuji.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Ambang batas: [batas_A, batas_B, batas_C]
#   A  = nilai <= batas_A
#   B  = > batas_A  dan <= batas_B
#   C  = > batas_B  dan <= batas_C
#   D  = > batas_C
# ---------------------------------------------------------------------------
NUTRI_LEVEL_MINUMAN = {          # per 100 mL (dari poster Kemenkes)
    "gula": [1.0, 5.0, 10.0],        # g       : A <=1   · B >1-5    · C >5-10    · D >10
    "natrium": [5.0, 120.0, 500.0],  # mg      : A <=5   · B >5-120  · C >120-500 · D >500
    "lemak_jenuh": [0.7, 1.2, 2.8],  # g       : A <=0,7 · B >0,7-1,2· C >1,2-2,8 · D >2,8
}

NUTRI_LEVEL_MAKANAN = {}         # per 100 g — ISI dari poster resmi (kosong = belum tersedia)

LEVEL_URUT = ["A", "B", "C", "D"]
LEVEL_WARNA = {"A": "#16A34A", "B": "#84CC16", "C": "#F59E0B", "D": "#EF4444"}
LEVEL_SEBUTAN = {
    "A": "RENDAH · lebih sehat",
    "B": "CUKUP RENDAH",
    "C": "CUKUP TINGGI",
    "D": "TINGGI · perlu dibatasi",
}
LEVEL_NAMA_ZAT = {"gula": "🍬 Gula", "natrium": "🧂 Garam (natrium)", "lemak_jenuh": "🥑 Lemak jenuh"}
LEVEL_SATUAN = {"gula": "g/100 mL", "natrium": "mg/100 mL", "lemak_jenuh": "g/100 mL"}


def level_zat(nilai: float, ambang_zat: list) -> str:
    """Satu zat gizi -> huruf A/B/C/D."""
    b1, b2, b3 = ambang_zat
    if nilai <= b1:
        return "A"
    if nilai <= b2:
        return "B"
    if nilai <= b3:
        return "C"
    return "D"


def level_terburuk(level_list) -> str:
    """Gabungan beberapa huruf -> yang terburuk (A < B < C < D)."""
    ada = [l for l in level_list if l in LEVEL_URUT]
    return max(ada, key=lambda l: LEVEL_URUT.index(l)) if ada else "A"


def ambang_untuk(jenis: str, ambang: dict | None = None) -> dict:
    """Ambil tabel ambang sesuai jenis produk ('minuman' = per 100 mL, 'makanan' = per 100 g)."""
    if ambang:
        return ambang
    return NUTRI_LEVEL_MINUMAN if jenis == "minuman" else NUTRI_LEVEL_MAKANAN


def per100(nilai_per_sajian: float, isi_sajian: float) -> float:
    """Ubah nilai per sajian menjadi nilai per 100 (mL untuk minuman / g untuk makanan)."""
    if not isi_sajian or isi_sajian <= 0:
        return float(nilai_per_sajian)
    return float(nilai_per_sajian) / float(isi_sajian) * 100.0


def tebak_jenis(takaran_saji: str | None) -> str:
    """Tebak minuman/makanan dari tulisan takaran saji ('250 ml' -> minuman)."""
    t = (takaran_saji or "").lower()
    if any(u in t for u in ("ml", "liter", "ltr", "l ")) or "ml" in t:
        return "minuman"
    return "makanan"


def baca_isi_sajian(takaran_saji: str | None) -> float | None:
    """Ambil angka isi sajian dari tulisan takaran saji ('250 ml' -> 250.0)."""
    import re
    if not takaran_saji:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|mL|ML|g|gr|gram|cc)", str(takaran_saji))
    if not m:
        return None
    try:
        return float(str(m.group(1)).replace(",", "."))
    except ValueError:
        return None


def nilai_per100(gula_sajian, natrium_sajian, lemak_jenuh_sajian,
                 isi_sajian: float, per100_langsung: dict | None = None) -> dict:
    """Hitung nilai per 100 mL/g. Kalau label sudah mencetak kolom per 100, pakai itu."""
    src = per100_langsung or {}
    return {
        "gula": float(src["gula"]) if src.get("gula") is not None
                else per100(gula_sajian or 0, isi_sajian),
        "natrium": float(src["natrium"]) if src.get("natrium") is not None
                else per100(natrium_sajian or 0, isi_sajian),
        "lemak_jenuh": float(src["lemak_jenuh"]) if src.get("lemak_jenuh") is not None
                else per100(lemak_jenuh_sajian or 0, isi_sajian),
    }


def analisis_nutri_level(gula_sajian=None, natrium_sajian=None, lemak_jenuh_sajian=None,
                         isi_sajian: float | None = None, jenis: str = "minuman",
                         ambang: dict | None = None, per100_langsung: dict | None = None) -> dict:
    """Hasil lengkap Nutri-Level untuk satu produk.

    Return dict:
      tersedia  : bool  -> False kalau ambang jenis produk ini belum diisi
      jenis     : 'minuman' | 'makanan'
      per100    : {gula, natrium, lemak_jenuh}
      level_zat : {gula: 'A'.., natrium: .., lemak_jenuh: ..}
      level     : huruf akhir produk (terburuk)
      lengkap   : bool -> apakah ketiga zat punya nilai
    """
    tabel = ambang_untuk(jenis, ambang)
    tabel = {k: v for k, v in (tabel or {}).items() if v}
    n100 = nilai_per100(gula_sajian, natrium_sajian, lemak_jenuh_sajian,
                        isi_sajian or 0, per100_langsung)
    langsung = per100_langsung or {}
    asli = {"gula": gula_sajian, "natrium": natrium_sajian, "lemak_jenuh": lemak_jenuh_sajian}
    level_zat_, kurang = {}, []
    for zat in ("gula", "natrium", "lemak_jenuh"):
        punya = (asli[zat] is not None) or (langsung.get(zat) is not None)
        if (zat in tabel) and punya:
            level_zat_[zat] = level_zat(n100[zat], tabel[zat])
        else:
            level_zat_[zat] = None
            kurang.append(zat)
    return {
        "tersedia": bool(tabel),
        "jenis": jenis,
        "per100": n100,
        "level_zat": level_zat_,
        "level": level_terburuk([v for v in level_zat_.values() if v]),
        "lengkap": len(kurang) == 0,
        "zat_kurang": kurang,
        "sumber": "HK.01.07/MENKES/301/2026 (Nutri-Level Kemenkes)",
        "satuan": "per 100 mL" if jenis == "minuman" else "per 100 g",
    }
