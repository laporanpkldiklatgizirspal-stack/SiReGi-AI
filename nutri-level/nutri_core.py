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
    "lemak_jenuh": {
        "pola": [
            re.compile(r"lemak\s+jenuh", re.I),
            re.compile(r"jenuh", re.I),
            re.compile(r"saturated\s+fat", re.I),
            re.compile(r"saturated", re.I),
        ],
        "hindari": re.compile(r"trans|tidak\s+jenuh|mono|poly|omega", re.I),
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


_BUKAN_NAMA = re.compile(
    r"^(informasi|nilai|gizi|nutrition|facts|takaran|sajian|serving|jumlah|energi|energy|lemak|fat|"
    r"protein|karbohidrat|carbohydrate|gula|sugar|natrium|sodium|garam|salt|kandungan|total|per|"
    r"disajikan|basis|dalam|kemasan|komposisi|ingredients?|bahan|akg|dv|%|no|kode|berat|netto|isi)",
    re.I,
)


def tebak_nama_produk(baris_list) -> Optional[str]:
    """Tebak nama produk dari baris teks label (dipakai kalau AI/OCR tak mengembalikan nama)."""
    for teks in baris_list or []:
        s = re.sub(r"\s+", " ", str(teks or "")).strip()
        if not (4 <= len(s) <= 60):
            continue
        if _BUKAN_NAMA.match(s) or _BARIS_LAIN.search(s):
            continue
        if s[0].isdigit() or re.search(r"[:=]\s*\d", s):
            continue
        huruf = len(re.findall(r"[A-Za-z]", s))
        if huruf < 3:
            continue
        if len(re.findall(r"\d", s)) > 4 and huruf < 8:
            continue
        return s[:60]
    return None


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
        "lemak_jenuh": None,
    }

    for kunci in ("energi", "protein", "karbohidrat", "lemak", "lemak_jenuh", "gula", "natrium"):
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

# (nama_package, nama_kelas) — urutan prioritas.
# 'rapidocr' DIKEMAS lokal di folder rapidocr/ (agar cloud tidak butuh
# opencv-python full/libGL); 'rapidocr_onnxruntime' tetap dicoba sbg cadangan.
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
            if nama_mod == "rapidocr":
                mod = _impor_rapidocr_dari_folder_mirip_cloud()
            else:
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


def _impor_rapidocr_dari_folder_mirip_cloud():
    """rapidocr DIKEMAS di folder aplikasi (nutri-level/rapidocr).

    Di Streamlit Cloud folder repo bisa read-only, padahal mesin OCR perlu
    menulis model yang belum ada (auto-download). Kalau folder models-nya
    tidak bisa ditulis -> salin seluruh package ke folder temp (writable)
    lalu import dari sana. Kalau bisa ditulis -> import biasa.
    """
    import importlib
    import shutil
    import sys
    import tempfile

    try:
        mod = importlib.import_module("rapidocr")
    except Exception:
        return None
    try:
        pkg_dir = os.path.dirname(mod.__file__)
        models_dir = os.path.join(pkg_dir, "models")
        uji = os.path.join(models_dir, ".tulis_uji")
        with open(uji, "w") as fh:
            fh.write("x")
        os.remove(uji)
        return mod  # writable — pakai langsung
    except Exception:
        pass  # read-only → salin ke temp

    cache = os.path.join(tempfile.gettempdir(), "rapidocr_vendor")
    try:
        if os.path.exists(cache):
            shutil.rmtree(cache, ignore_errors=True)
        shutil.copytree(pkg_dir, cache)
        for k in [k for k in list(sys.modules)
                  if k == "rapidocr" or k.startswith("rapidocr.")]:
            sys.modules.pop(k, None)
        parent = os.path.dirname(cache)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        return importlib.import_module("rapidocr")
    except Exception:
        return mod


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
Label bisa ditulis 2 bahasa (Indonesia + Inggris) dengan kolom %AKG/%DV — ABAIKAN kolom persen.
Baca label pada foto, lalu jawab HANYA JSON valid tanpa teks lain:
{
  "nama_produk": "nama produk atau null",
  "takaran_saji": "contoh: 250 ml / 1 bungkus (35 g) atau null",
  "isi_saji_ml_atau_g": 250,
  "sajian_per_kemasan": 2,
  "energi_total_kkal": 180,
  "protein_g": 3,
  "karbohidrat_total_g": 12,
  "lemak_total_g": 4,
  "lemak_jenuh_g": 1.5,
  "gula_g": 18,
  "natrium_mg": 120,
  "per100_gula_g": null,
  "per100_natrium_mg": null,
  "per100_lemak_jenuh_g": null
}
Aturan:
- Nilai sesuai TAKARAN SAJI yang tercetak (bukan per 100 g, kecuali label memang per 100 g).
- "isi_saji_ml_atau_g" = isi satu sajian dalam mL (minuman) atau gram (makanan), diambil dari takaran saji.
- Gula = Gula/Gula Total/Sugars/Total Sugars (JANGAN gula alkohol).
- Natrium = Natrium/Garam (Natrium)/Sodium/Salt.
- Lemak total = Lemak Total/Total Fat (JANGAN lemak jenuh/trans).
- Lemak jenuh = Lemak Jenuh/Saturated Fat (JANGAN lemak trans).
- Kalau label IKUT mencetak kolom "per 100 g / per 100 mL", isi per100_* dengan angka kolom itu; kalau tidak ada, isi null.
- Kalau satu angka tidak terbaca/ragu, isi null (bukan perkiraan).
- Angka pakai titik desimal (contoh 4.5)."""

# Nama model Gemini yang dicoba berurutan (2026: 2.0 bisa sudah pensiun)
_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]


class GeminiGagal(Exception):
    pass


def _mime_gambar(byte_gambar: bytes) -> str:
    """Tebak tipe gambar dari beberapa byte pertama (PNG vs JPEG)."""
    if byte_gambar[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"


def _gemini_baca_multi(daftar_gambar, api_key: str, prompt: str):
    """Kirim 1..N foto + prompt ke Gemini. Return (data_json, nama_model)."""
    bagian = [{"text": prompt}]
    for g in daftar_gambar:
        bagian.append({"inline_data": {"mime_type": _mime_gambar(g),
                                       "data": base64.b64encode(g).decode()}})
    kendala = []
    for model in _GEMINI_MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": bagian}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1024},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            teks = data["candidates"][0]["content"]["parts"][0]["text"]
            awal, akhir = teks.find("{"), teks.rfind("}")
            if awal == -1 or akhir == -1:
                raise ValueError("jawaban bukan JSON")
            return json.loads(teks[awal:akhir + 1]), model
        except urllib.error.HTTPError as e:
            try:
                pesan = json.loads(e.read().decode()).get("error", {}).get("message", "")
            except Exception:
                pesan = ""
            kendala.append(f"{model}: HTTP {e.code} {pesan}")
        except Exception as exc:
            kendala.append(f"{model}: {type(exc).__name__}: {exc}")
    raise GeminiGagal(" ; ".join(kendala))


def _gemini_baca(byte_gambar: bytes, api_key: str):
    return _gemini_baca_multi([byte_gambar], api_key, _PROMPT_GEMINI)


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
        "sajian_per_kemasan": ("sajian_per_kemasan", "jumlah_sajian_per_kemasan", "servings_per_package", "sajian"),
        "energi": ("energi_total_kkal", "energi_kkal", "energy_kcal", "energi"),
        "protein": ("protein_g", "protein"),
        "karbohidrat": ("karbohidrat_total_g", "carbohydrate_g", "karbohidrat"),
        "gula": ("gula_g", "gula_total_g", "sugar_g", "total_sugar_g", "sugars_g"),
        "lemak_jenuh": ("lemak_jenuh_g", "saturated_fat_g", "lemak_jenuh", "saturated_fat"),
        "natrium": ("natrium_mg", "sodium_mg", "garam_natrium_mg", "salt_mg", "natrium", "sodium"),
        "lemak": ("lemak_total_g", "fat_total_g", "total_fat_g", "lemak_g", "fat_g", "lemak"),
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
    # nilai kolom "per 100 g/mL" kalau label mencetaknya
    per100 = {}
    for kunci_core, kandidat in {
        "gula": ("per100_gula_g", "gula_per100_g"),
        "natrium": ("per100_natrium_mg", "natrium_per100_mg"),
        "lemak_jenuh": ("per100_lemak_jenuh_g", "lemak_jenuh_per100_g"),
    }.items():
        for k in kandidat:
            v = data.get(k)
            if v in (None, "", "null"):
                continue
            try:
                per100[kunci_core] = round(float(v), 2)
            except (TypeError, ValueError):
                continue
            break
    if per100:
        hasil["_per100"] = per100
    # isi satu sajian (mL untuk minuman / g untuk makanan)
    for k in ("isi_saji_ml_atau_g", "isi_saji", "isi_saji_g", "isi_saji_ml"):
        v = data.get(k)
        if v in (None, "", "null"):
            continue
        try:
            hasil["isi_sajian"] = float(v)
        except (TypeError, ValueError):
            continue
        break
    return hasil


# ---------------------------------------------------------------------------
# Fungsi utama pembaca label
# ---------------------------------------------------------------------------
# Field yang harus terisi otomatis (dipakai untuk cek kelengkapan & putaran kedua)
FIELD_PENTING = ("nama_produk", "takaran_saji", "gula", "natrium", "lemak", "lemak_jenuh")

_PROMPT_LENGKAPI = """\
Kamu pembaca label Informasi Nilai Gizi (nutrition facts) yang teliti.
Foto bisa berupa beberapa sisi produk yang sama (mis. kemasan depan + tabel gizi).
ABAIKAN kolom %AKG / %DV.
Angka yang BELUM terbaca: {kurang}.
Baca ULANG foto dengan teliti, lalu jawab HANYA JSON valid tanpa teks lain:
{
  "nama_produk": "nama produk atau null",
  "takaran_saji": "contoh: 250 ml / 1 bungkus (35 g) atau null",
  "isi_saji_ml_atau_g": null,
  "sajian_per_kemasan": null,
  "lemak_total_g": null,
  "lemak_jenuh_g": null,
  "gula_g": null,
  "natrium_mg": null
}
Aturan:
- Isi HANYA angka yang benar-benar terbaca & yakin; yang ragu isi null (jangan mengira-ngira).
- Nilai sesuai takaran saji yang tercetak.
- Gula = Gula/Total Sugars (bukan gula alkohol) · Natrium = Natrium/Sodium ·
  Lemak total = Lemak Total/Total Fat (bukan jenuh/trans) · Lemak jenuh = Lemak Jenuh/Saturated Fat.
- Angka pakai titik desimal (contoh 4.5)."""


def field_kurang(hasil: dict) -> list:
    """Daftar field penting yang masih kosong pada hasil pembacaan."""
    kurang = []
    for k in FIELD_PENTING:
        v = (hasil or {}).get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            kurang.append(k)
    return kurang


def gabung_hasil(utama: dict, tambahan: dict) -> dict:
    """Isi field yang masih kosong di `utama` memakai nilai dari `tambahan`."""
    gab = dict(utama or {})
    for k, v in (tambahan or {}).items():
        if k.startswith("_"):
            continue
        if v is None or v == "" or v == "null":
            continue
        sekarang = gab.get(k)
        if k == "sajian_per_kemasan":
            if sekarang in (None, 0, 1) and float(v or 0) > 1:
                gab[k] = v
            continue
        if sekarang is None or sekarang == "":
            gab[k] = v
    # gabungkan kolom per 100 (kalau ada di salah satu)
    p1 = dict(utama.get("_per100") or {})
    p2 = dict((tambahan or {}).get("_per100") or {})
    p1.update({k: v for k, v in p2.items() if v is not None})
    if p1:
        gab["_per100"] = p1
    return gab


def read_nutrition_label(byte_gambar: bytes, gemini_key: Optional[str] = None,
                        gambar_tambahan: Optional[list] = None) -> dict:
    """Baca label dari 1..N foto (PNG/JPEG dari kamera).

    - Semua foto dikirim sekaligus (mis. kemasan depan + tabel gizi) supaya AI punya
      konteks lebih banyak.
    - Kalau masih ada field penting yang kosong, dicoba PUTARAN KEDUA dengan prompt
      yang menyebut field mana yang belum terbaca.
    - Tanpa kunci AI / AI gagal -> OCR lokal pada semua foto, hasilnya digabung.

    Mengembalikan dict hasil scan dengan kunci standar + '_sumber' + '_baris' + '_kurang'.
    """
    daftar = [g for g in ([byte_gambar] + list(gambar_tambahan or [])) if g]

    if gemini_key:
        catatan = None
        try:
            data, model = _gemini_baca_multi(daftar, gemini_key, _PROMPT_GEMINI)
            if data:
                hasil = _gemini_ke_hasil(data)
                hasil["_sumber"] = f"gemini:{model}"
                hasil["_baris"] = []
                # putaran kedua: khusus mengisi yang masih kosong
                kurang = field_kurang(hasil)
                if kurang:
                    try:
                        prompt2 = _PROMPT_LENGKAPI.replace("{kurang}", ", ".join(kurang))
                        data2, model2 = _gemini_baca_multi(daftar, gemini_key, prompt2)
                        if data2:
                            hasil = gabung_hasil(hasil, _gemini_ke_hasil(data2))
                            hasil["_sumber"] = f"gemini:{model2} (2 putaran)"
                    except Exception as exc2:
                        hasil["_gemini_error2"] = f"{type(exc2).__name__}: {exc2}"
                hasil["_kurang"] = field_kurang(hasil)
                if len(daftar) > 1:
                    hasil["_jumlah_foto"] = len(daftar)
                return hasil
        except GeminiGagal as exc:
            catatan = str(exc)
        except Exception as exc:
            catatan = f"{type(exc).__name__}: {exc}"
        # Gemini gagal -> jatuh ke OCR lokal (semua foto), tapi catat alasannya
        try:
            hasil = _ocr_gabung(daftar)
            hasil["_gemini_error"] = catatan
            hasil["_kurang"] = field_kurang(hasil)
            return hasil
        except Exception as exc:
            return {
                "gula": None, "natrium": None, "lemak": None, "lemak_jenuh": None,
                "protein": None, "karbohidrat": None, "energi": None,
                "takaran_saji": None, "sajian_per_kemasan": 1, "nama_produk": None,
                "_baris": [], "_sumber": "gagal", "_kurang": list(FIELD_PENTING),
                "_gemini_error": catatan,
                "_ocr_error": str(exc),
            }

    hasil = _ocr_gabung(daftar)
    hasil["_kurang"] = field_kurang(hasil)
    return hasil


def _ocr_gabung(daftar_gambar: list) -> dict:
    """OCR lokal untuk semua foto, hasilnya digabung (field kosong diisi dari foto lain)."""
    hasil, baris_semua = {}, []
    for g in daftar_gambar:
        baris = ocr_ke_baris(g)
        baris_semua += baris
        hasil = gabung_hasil(hasil, parse_label_baris(baris))
    hasil["_sumber"] = "ocr"
    hasil["_baris"] = baris_semua
    # tebak nama produk hanya kalau angka gizinya kebaca (kalau OCR kacau, nama bisa sampah)
    if not hasil.get("nama_produk") and sum(
            1 for k in ("gula", "natrium", "lemak") if hasil.get(k) is not None) >= 2:
        hasil["nama_produk"] = tebak_nama_produk(baris_semua)
    if len(daftar_gambar) > 1:
        hasil["_jumlah_foto"] = len(daftar_gambar)
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
