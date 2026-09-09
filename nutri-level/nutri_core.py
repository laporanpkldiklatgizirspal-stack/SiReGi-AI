"""
Nutri Level — inti logika (OCR pembaca label + parser + analisis level nutrisi).

Dipisah dari app.py supaya gampang diuji tanpa Streamlit.

Alur:
  1. read_nutrition_label(byte_gambar, gemini_key=None)  -> dict hasil scan
     - kalau gemini_key diisi  -> coba AI Vision Gemini (paling akurat)
     - kalau tidak / gagal     -> OCR lokal RapidOCR (privat, tanpa API key)
  2. parse_label_baris(baris_teks) -> struktur nilai gizi dari teks OCR
  3. analisis_produk(...)          -> persen batas harian + status warna
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.request
from typing import Optional

# ---------------------------------------------------------------------------
# Konfigurasi bawaan (bisa diubah lewat UI aplikasi)
# ---------------------------------------------------------------------------
DAILY_LIMITS = {
    "sugar_g": 50.0,    # gula        -> gram per hari (WHO, 2000 kkal)
    "sodium_mg": 2000.0,  # natrium   -> mg per hari
    "fat_g": 67.0,        # lemak total -> gram per hari (30% energi)
}

STATUS_THRESHOLDS = {
    "warning": 50.0,   # >= 50%  -> kuning
    "danger": 100.0,   # >= 100% -> merah
}

# Meta zat gizi yang dianalisis (urutan tampilan)
NUTRIENTS = [
    {"key": "gula",    "emoji": "🍬", "label": "GULA",        "unit": "g",  "limit_key": "sugar_g"},
    {"key": "natrium", "emoji": "🧂", "label": "NATRIUM",     "unit": "mg", "limit_key": "sodium_mg"},
    {"key": "lemak",   "emoji": "🥑", "label": "LEMAK TOTAL", "unit": "g",  "limit_key": "fat_g"},
]

# ---------------------------------------------------------------------------
# Parser teks label
# ---------------------------------------------------------------------------
_ANGKA = r"\d+(?:[.,]\d+)?"
_SATUAN = r"(?:mcg|µg|mg|gr|gram|grams?|g|kkal|kcal|ml|%)"

# Pola per zat gizi: alias paling spesifik duluan.
_FIELD_SPEC = {
    "gula": {
        "pola": [
            re.compile(r"gula\s+total", re.I),
            re.compile(r"total\s+gula", re.I),
            re.compile(r"total\s+sugars?", re.I),
            re.compile(r"sugars?\s+total", re.I),
            re.compile(r"added\s+sugars?", re.I),
            re.compile(r"\bgula\b", re.I),
            re.compile(r"\bsugars?\b", re.I),
        ],
        "hindari": re.compile(r"alkohol|alcohol|serat|fiber", re.I),
        "satuan": "g",
    },
    "natrium": {
        "pola": [
            re.compile(r"\bnatrium\b", re.I),
            re.compile(r"\bsodium\b", re.I),
            re.compile(r"\bna\b", re.I),
        ],
        "hindari": re.compile(r"klorida|chloride", re.I),
        "satuan": "mg",
    },
    "lemak": {
        "pola": [
            re.compile(r"lemak\s+total", re.I),
            re.compile(r"total\s+lemak", re.I),
            re.compile(r"total\s+fat", re.I),
            re.compile(r"\blemak\b", re.I),
            re.compile(r"\bfat\b", re.I),
        ],
        "hindari": re.compile(r"jenuh|saturated|trans|tidak\s+jenuh|mono|poly|omega|kolesterol|cholesterol", re.I),
        "satuan": "g",
    },
    "protein": {
        "pola": [re.compile(r"\bprotein\b", re.I)],
        "hindari": None,
        "satuan": "g",
    },
    "karbohidrat": {
        "pola": [
            re.compile(r"karbohidrat\s+total", re.I),
            re.compile(r"total\s+karbohidrat", re.I),
            re.compile(r"carbohydrates?\s+total", re.I),
            re.compile(r"\bkarbohidrat\b", re.I),
            re.compile(r"\bcarbohydrates?\b", re.I),
        ],
        "hindari": re.compile(r"serat|fiber|gula\b", re.I),
        "satuan": "g",
    },
    "energi": {
        "pola": [
            re.compile(r"energi\s+total", re.I),
            re.compile(r"total\s+energi", re.I),
            re.compile(r"\benergi\b", re.I),
            re.compile(r"\benergy\b", re.I),
        ],
        "hindari": None,
        "satuan": "kkal",
    },
}

# Baris yang "berbau" baris label lain -> jangan dipakai sebagai nilai
# dari baris tetangga (menghindari salah ambil angka kolom sebelah).
_BARIS_LAIN = re.compile(
    r"gula|sugars?|natrium|sodium|lemak|fat|protein|karbohidrat|carb|energi|energy"
    r"|saji|kemasan|serving|serat|fiber|jenuh|saturated|trans|kolesterol|cholesterol",
    re.I,
)

_POLA_TAKARAN_SAJI = re.compile(r"takaran\s+saji|ukuran\s+saji|per\s+sajian|serving\s+size", re.I)
_POLA_SAJIAN_KEMASAN = re.compile(
    r"jumlah\s+sajian?\s+per\s+kemasan|sajian?\s+per\s+kemasan|sajian?\s+dalam\s+kemasan"
    r"|servings?\s+per\s+(?:package|container|pouch|box|bag)",
    re.I,
)


def _float_id(s: str) -> Optional[float]:
    """'18' -> 18.0 ; '18,5' -> 18.5 ; '1.250' -> 1250.0"""
    s = s.strip().replace(" ", "")
    if not re.fullmatch(r"-?\d+(?:[.,]\d+)?", s):
        return None
    if "," in s and "." in s:
        # 1.250,5 -> buang titik ribu, koma jadi desimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def _token_angka(teks: str):
    """Semua (nilai, satuan) yang muncul di sebaris teks, satuan dicari dulu."""
    hasil = []
    for m in re.finditer(rf"({_ANGKA})\s*({_SATUAN})?\b", teks, re.I):
        if m.group(2) and m.group(2).lower() in ("%",):
            continue
        val = _float_id(m.group(1))
        if val is not None:
            hasil.append((val, (m.group(2) or "").lower() or None))
    return hasil


def _keluarga_satuan(satuan: Optional[str]) -> str:
    if satuan is None:
        return ""
    if satuan in ("mg", "mcg", "µg"):
        return "mg"
    if satuan in ("g", "gr", "gram", "grams"):
        return "g"
    if satuan in ("kkal", "kcal"):
        return "kkal"
    return ""


def _konversi_ke_satuan(nilai: float, satuan: Optional[str], target: str) -> float:
    """Ubah nilai ke satuan target ('g' atau 'mg' atau 'kkal')."""
    fam = _keluarga_satuan(satuan)
    if fam == "g" and target == "mg":
        return nilai * 1000.0
    if fam == "mg" and target == "g":
        return nilai / 1000.0
    return nilai


def _ambil_nilai_baris(teks: str, target: str, m_kata=None):
    """Ambil angka+satuan dari satu baris teks.

    - Kalau ketemu satuan sesuai target -> pakai.
    - Kalau tidak ada satuan sama sekali -> angka pertama (anggap target).
    - Kalau satuannya beda (mis. mg untuk target g) -> abaikan.
    """
    tokens = _token_angka(teks)
    if not tokens:
        return None
    target_fam = _keluarga_satuan(target) or target
    # 1) angka yang satuannya cocok dengan target
    for val, sat in tokens:
        fam = _keluarga_satuan(sat)
        if sat is not None and fam == target_fam:
            return _konversi_ke_satuan(val, sat, target)
    # 2) angka polos (tanpa satuan) di baris target: ambil yang terdekat dgn kata kunci
    if m_kata:
        pos = m_kata.end()
        for val, sat in tokens:
            if sat is None:
                return val  # satu angka polos cukup
    # 3) angka polos apa pun
    for val, sat in tokens:
        if sat is None:
            return val
    return None


def _cari_zat(baris_list, spec, target_satuan):
    """Cari nilai zat gizi di daftar baris. return (nilai, baris_yang_cocok)"""
    for pola in spec["pola"]:
        for i, teks in enumerate(baris_list):
            m = pola.search(teks)
            if not m:
                continue
            if spec["hindari"] and spec["hindari"].search(teks):
                continue
            # nomor harus berada di sisi kanan dari kata kunci (nilai label)
            kanan = teks[m.end():]
            nilai = _ambil_nilai_baris(kanan, target_satuan, m)
            if nilai is None:
                # coba ambil dari seluruh baris (kalau kata kunci di tengah)
                nilai = _ambil_nilai_baris(teks, target_satuan, m)
            # kalau baris ini tidak ada angkanya, intip 1-2 baris berikutnya
            if nilai is None:
                for j in range(i + 1, min(i + 3, len(baris_list))):
                    nxt = baris_list[j]
                    if _BARIS_LAIN.search(nxt):
                        break
                    nilai = _ambil_nilai_baris(nxt, target_satuan)
                    if nilai is not None:
                        break
            if nilai is not None:
                return round(nilai, 2), teks
    return None, None


def _teks_nilai_mentah(teks: str, m) -> Optional[str]:
    seg = teks[m.end():]
    seg = seg.strip(" :–—-\t")
    seg = re.sub(r"\s+", " ", seg)
    if not seg:
        return None
    return seg[:60]


def parse_label_baris(baris_list):
    """Ubah daftar baris hasil OCR jadi struktur nilai gizi."""
    bersih = [b.strip() for b in baris_list if b and b.strip()]
    hasil = {
        "nama_produk": None,
        "takaran_saji": None,
        "sajian_per_kemasan": 1,
        "energi": None,
        "protein": None,
        "karbohidrat": None,
        "gula": None,
        "natrium": None,
        "lemak": None,
    }

    for kunci in ("energi", "protein", "karbohidrat", "lemak", "gula", "natrium"):
        spec = _FIELD_SPEC[kunci]
        nilai, _baris = _cari_zat(bersih, spec, spec["satuan"])
        hasil[kunci] = nilai

    # --- Takaran saji ---
    for i, teks in enumerate(bersih):
        if _BARIS_LAIN.search(teks) and not _POLA_TAKARAN_SAJI.search(teks):
            continue
        m = _POLA_TAKARAN_SAJI.search(teks)
        if m:
            mentah = _teks_nilai_mentah(teks, m) or None
            if mentah is None and i + 1 < len(bersih):
                mentah = bersih[i + 1][:60]
            hasil["takaran_saji"] = mentah
            break

    # --- Jumlah sajian per kemasan ---
    for i, teks in enumerate(bersih):
        m = _POLA_SAJIAN_KEMASAN.search(teks)
        if not m:
            continue
        kanan = teks[m.end():]
        if not kanan and i + 1 < len(bersih):
            kanan = bersih[i + 1]
        for val, sat in _token_angka(kanan):
            if 1 <= val <= 60:
                hasil["sajian_per_kemasan"] = int(round(val))
                break
        break  # satu baris "sajian per kemasan" saja yang dipakai

    return hasil


# ---------------------------------------------------------------------------
# OCR lokal (dua mesin: rapidocr unified utk semua Python >= 3.8,
# fallback rapidocr-onnxruntime utk Python lama) — tanpa API key
# ---------------------------------------------------------------------------
_OCR_ENGINE = None
_OCR_GAGAL = None
_OCR_TERAKHIR = None

# (nama_package, nama_kelas) — urutan prioritas
_ENGINE_CANDIDATES = [
    ("rapidocr", "RapidOCR"),
    ("rapidocr_onnxruntime", "RapidOCR"),
]


def _dapat_engine():
    global _OCR_ENGINE, _OCR_GAGAL, _OCR_TERAKHIR
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE
    if _OCR_GAGAL:
        raise RuntimeError(_OCR_GAGAL)
    masalah = []
    for nama_mod, nama_cls in _ENGINE_CANDIDATES:
        try:
            mod = __import__(nama_mod, fromlist=[nama_cls])
            _OCR_ENGINE = getattr(mod, nama_cls)()
            _OCR_TERAKHIR = nama_mod
            return _OCR_ENGINE
        except Exception as exc:  # pragma: no cover
            masalah.append(f"{nama_mod}: {type(exc).__name__}: {exc}")
    import sys

    _OCR_GAGAL = (
        "Mesin OCR tidak bisa dipakai di server ini. "
        "Pastikan package terpasang: pip install rapidocr"
        + " | detail: " + " || ".join(masalah)
        + f" | python {sys.version.split()[0]}"
    )
    raise RuntimeError(_OCR_GAGAL)


def ocr_ke_baris(byte_gambar: bytes):
    """Gambar (PNG/JPEG) -> daftar baris teks yang terbaca."""
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(byte_gambar)).convert("RGB")
    hasil = _dapat_engine()(np.array(img))

    # Normalisasi output dua generasi rapidocr:
    # - rapidocr (unified) >= 3.x -> objek RapidOCROutput (.boxes/.txts/.scores)
    # - rapidocr_onnxruntime   -> tuple (items, elapse); items = [box, teks, skor]
    items = []
    if hasattr(hasil, "txts"):
        for box, teks, skor in zip(hasil.boxes, hasil.txts, hasil.scores):
            try:
                bbox = [list(map(float, p)) for p in box]
            except (TypeError, ValueError):
                continue
            items.append((bbox, str(teks), float(skor)))
    else:
        items = list((hasil or ([], None))[0] or [])

    # urutkan baris: atas -> bawah, lalu kiri -> kanan (dikelompokkan per baris)
    terurut = []
    for box, teks, _skor in items:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        terurut.append((min(ys), min(xs), str(teks)))
    terurut.sort(key=lambda t: (round(t[0] / 12), t[1]))
    return [t[2] for t in terurut]


# ---------------------------------------------------------------------------
# AI Vision Gemini (opsional, dipakai kalau ada GEMINI_API_KEY)
# ---------------------------------------------------------------------------
_PROMPT_GEMINI = """\
Kamu adalah pembaca label Informasi Nilai Gizi (nutrition facts) yang teliti.
Baca label pada foto, lalu jawab HANYA JSON valid tanpa teks lain:
{
  "nama_produk": "nama produk atau null",
  "takaran_saji": "contoh: 250 ml / 1 bungkus (35 g) atau null",
  "sajian_per_kemasan": 2,
  "energi_total_kkal": 180,
  "protein_g": 3,
  "karbohidrat_total_g": 12,
  "lemak_total_g": 4,
  "gula_g": 18,
  "natrium_mg": 120
}
Aturan:
- Nilai sesuai TAKARAN SAJI yang tercetak (bukan per 100 g, kecuali label memang per 100 g).
- Kalau satu angka tidak terbaca/ragu, isi null (bukan perkiraan).
- Gula = Total Gula/Sugars; Natrium = Natrium/Sodium; Lemak = Lemak Total/Total Fat.
- Angka pakai titik desimal (contoh 4.5)."""


def _gemini_baca(byte_gambar: bytes, api_key: str):
    b64 = base64.b64encode(byte_gambar).decode()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _PROMPT_GEMINI},
                    {"inline_data": {"mime_type": "image/png", "data": b64}},
                ]
            }
        ],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1024},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode())
    teks = data["candidates"][0]["content"]["parts"][0]["text"]
    awal, akhir = teks.find("{"), teks.rfind("}")
    if awal == -1 or akhir == -1:
        return None
    return json.loads(teks[awal:akhir + 1])


def _gemini_ke_hasil(data: dict) -> dict:
    hasil = {
        "nama_produk": data.get("nama_produk"),
        "takaran_saji": data.get("takaran_saji"),
        "sajian_per_kemasan": None,
        "energi": None,
        "protein": None,
        "karbohidrat": None,
        "gula": None,
        "natrium": None,
        "lemak": None,
    }
    peta = {
        "sajian_per_kemasan": ("sajian_per_kemasan", "servings_per_package"),
        "energi": ("energi_total_kkal", "energi_kkal", "energy_kcal"),
        "protein": ("protein_g", "protein"),
        "karbohidrat": ("karbohidrat_total_g", "carbohydrate_g"),
        "gula": ("gula_g", "sugar_g", "sugars_g"),
        "natrium": ("natrium_mg", "sodium_mg"),
        "lemak": ("lemak_total_g", "fat_g"),
    }
    for kunci, kandidat in peta.items():
        for k in kandidat:
            v = data.get(k)
            if v in (None, "", "null"):
                continue
            try:
                if kunci == "sajian_per_kemasan":
                    hasil[kunci] = int(round(float(v)))
                else:
                    hasil[kunci] = round(float(v), 2)
            except (TypeError, ValueError):
                continue
            break
    if hasil["sajian_per_kemasan"] in (None, 0):
        hasil["sajian_per_kemasan"] = 1
    return hasil


# ---------------------------------------------------------------------------
# Fungsi utama pembaca label
# ---------------------------------------------------------------------------
def read_nutrition_label(byte_gambar: bytes, gemini_key: Optional[str] = None) -> dict:
    """Baca label dari byte gambar (PNG/JPEG dari kamera).

    Mengembalikan dict hasil scan dengan kunci standar + '_sumber' + '_baris'.
    Kalau tidak ada yang terbaca sama sekali -> dict nilai None.
    """
    if gemini_key:
        try:
            data = _gemini_baca(byte_gambar, gemini_key)
            if data:
                hasil = _gemini_ke_hasil(data)
                hasil["_sumber"] = "gemini"
                hasil["_baris"] = []
                return hasil
        except Exception:
            pass  # jatuh ke OCR lokal

    baris = ocr_ke_baris(byte_gambar)
    hasil = parse_label_baris(baris)
    hasil["_sumber"] = "ocr"
    hasil["_baris"] = baris
    return hasil


# ---------------------------------------------------------------------------
# Analisis level nutrisi
# ---------------------------------------------------------------------------
def status_persen(persen: float, ambang: dict) -> str:
    if persen >= ambang["danger"]:
        return "merah"
    if persen >= ambang["warning"]:
        return "kuning"
    return "hijau"


_STATUS_TEXT = {
    "hijau": ("🟢 HIJAU", "Aman"),
    "kuning": ("🟡 KUNING", "Perlu perhatian"),
    "merah": ("🔴 MERAH", "Melebihi batas harian"),
}


def stat_nutrisi(nilai: float, batas: float, ambang: dict, skala: float = 1.0) -> dict:
    """skala=1 untuk per sajian; skala=sajian_per_kemasan untuk 1 kemasan penuh."""
    nilai_total = nilai * skala
    persen = (nilai_total / batas * 100.0) if batas else 0.0
    warna = status_persen(persen, ambang)
    badge, pesan = _STATUS_TEXT[warna]
    return {
        "nilai": round(nilai_total, 2),
        "persen": persen,
        "warna": warna,
        "badge": badge,
        "pesan": pesan,
    }


def analisis_produk(data: dict, limits: Optional[dict] = None,
                    ambang: Optional[dict] = None) -> dict:
    """Hitung level per sajian & per kemasan utk semua zat gizi utama."""
    limits = limits or dict(DAILY_LIMITS)
    ambang = ambang or dict(STATUS_THRESHOLDS)
    sajian = int(data.get("sajian_per_kemasan") or 1)
    per_sajian, per_kemasan = {}, {}
    for meta in NUTRIENTS:
        kunci = meta["key"]
        nilai = data.get(kunci)
        if nilai is None:
            per_sajian[kunci] = None
            per_kemasan[kunci] = None
            continue
        batas = limits[meta["limit_key"]]
        per_sajian[kunci] = stat_nutrisi(float(nilai), batas, ambang, 1.0)
        per_kemasan[kunci] = stat_nutrisi(float(nilai), batas, ambang, sajian)

    ada_merah = any(
        s and s["warna"] == "merah" for s in list(per_sajian.values()) + list(per_kemasan.values())
    )
    return {
        "per_sajian": per_sajian,
        "per_kemasan": per_kemasan,
        "sajian_per_kemasan": sajian,
        "ada_merah": ada_merah,
    }
