# -*- coding: utf-8 -*-
"""Buku Foto Makanan Kemenkes (SKMI 2014) -> katalog porsi URT (Ukuran Rumah Tangga).

Data diambil dari PDF Buku Foto Makanan (folder Downloads):
  - data/daftar_buku_foto.json   : daftar 240 item makanan + path foto JPEG
  - data/ocr_buku_foto/bf_NNN.txt: hasil OCR tiap halaman (keterangan porsi+gram)
  - data/urt_buku_foto.json      : hasil parsing OCR -> porsi URT per item
                                    {"kode": ..., "nama": ..., "porsi": [{"label","gram"}], ...}

Kegunaan: pasien/masyarakat memilih porsi dari FOTO (1 porsi kecil/sedang/besar,
1 potong dada atas, 1 gelas, ...), aplikasi mengonversi ke gram, lalu zat gizi
dihitung dari database TKPI (per 100 g BDD).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from utils import ai_recall as air

_BASE = Path(__file__).resolve().parent.parent

# Kata generik berbobot kecil saat pencocokan (lihat ai_recall.KATA_UMUM_BAHAN)
_KATA_UMUM = air.KATA_UMUM_BAHAN

DAFTAR_FILE = _BASE / "data" / "daftar_buku_foto.json"
URT_FILE = _BASE / "data" / "urt_buku_foto.json"
OCR_DIR = _BASE / "data" / "ocr_buku_foto"

# Nama kategori (huruf pertama kode item di buku)
KATEGORI_NAMA = {
    "A": "🍚 Sumber Karbohidrat",
    "B": "🍗 Protein / Lauk",
    "C": "🥬 Sayuran",
    "D": "🍎 Buah",
    "E": "🍰 Kue & Jajanan",
    "F": "🍜 Makanan Siap Saji",
    "G": "🥤 Minuman",
    "": "Lainnya",
}

_REG_OPT = re.compile(r"^([A-Za-z])[\.\)]\s*(.+)$")
# kode item di judul halaman: "A1. Nasi Putih", "B.9 Ayam Goreng Dada" (huruf
# langsung angka, atau angka lalu titik) — BUKAN opsi foto
_REG_KODE_ITEM = re.compile(r"^[A-Za-z]\.?\d+[\.\)]")
_REG_KODE_ITEM2 = re.compile(r"^[A-Za-z]\d+[\s\.\)]")
_REG_OPT2 = re.compile(r"^([A-Za-z])\s+(\d)", re.IGNORECASE)  # "R 1 Gelas" (huruf + angka, tanpa titik)
_REG_GR = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:g|gr|gram|cc|ml)\b", re.IGNORECASE)
_REG_GR2 = re.compile(r"(?:=|:|\u2192|\u2248)\s*(\d+(?:[.,]\d+)?)")
# opsi tunggal tanpa huruf: "1 bh", "1 ptg", "1 gelas", "1 mangkok", dst
_REG_SATUAN_OPT = re.compile(
    r"^\d+(?:[.,]\d+)?\s*(bh|ptg|pt|buah|butir|gelas|mangkok|mangkuk|piring|centong|"
    r"potong|iris|lembar|porsi|ekor|kepal|sendok|sdm|sdt|cangkir|kotak|bks|bungkus)\b",
    re.IGNORECASE,
)


def muat_daftar() -> list[dict]:
    """Daftar item buku foto: [{kode, nama, kategori, halaman_pdf, foto, kb}]."""
    if not DAFTAR_FILE.exists():
        return []
    try:
        return json.loads(DAFTAR_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _teks_ocr(kode: str) -> str:
    fp = OCR_DIR / f"{kode}.txt"
    if not fp.exists():
        return ""
    return fp.read_text(encoding="utf-8", errors="ignore")


def parse_ocr_ke_porsi(teks: str, kategori: str = "", nama_item: str = "") -> list[dict]:
    """Parse hasil OCR halaman -> daftar porsi [{label, gram, ket}].

    Pola umum halaman buku: foto diberi huruf A/B/C dengan keterangan
    (mis. 'A. 1 Porsi Besar') dan angka gram di baris lain ('300 g').
    Minuman memakai 'cc'/'ml' (1 cc ≈ 1 g untuk cairan, gram = angka sama).
    Halaman kue/jajanan sering hanya '1 bh / 70 g' (opsi tunggal).
    Bila label huruf tidak terbaca OCR (huruf ada di dalam foto / baris 'A.'
    terpisah), untuk kategori makanan A-D dipakai urutan keterangan/satuan
    -> dianggap opsi A, B, C, ...
    Gram dicocokkan berurutan dari opsi pertama; bila angka kurang, sisanya
    gram=None (perlu cek manual).
    """
    if not teks:
        return []
    baris = []
    for b in teks.splitlines():
        b = b.strip()
        # OCR sering membaca angka 1 sebagai huruf I/l/O saat berdiri sendiri
        b = re.sub(r"(?<![a-zA-Z])[IlOo](?![a-zA-Z])", "1", b)
        if b:
            baris.append(b)
    # angka berat: semua nilai gram/cc/ml dari baris mana pun
    angka = []
    for b in baris:
        for m in _REG_GR.finditer(b):
            try:
                angka.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                pass
    if not angka:
        for b in baris:
            for m in _REG_GR2.finditer(b):
                try:
                    angka.append(float(m.group(1).replace(",", ".")))
                except ValueError:
                    pass
    # baris yang seluruhnya angka polos ("150") tanpa satuan — berat makanan
    if not angka:
        for b in baris:
            if re.fullmatch(r"\d+(?:[.,]\d+)?", b):
                try:
                    angka.append(float(b.replace(",", ".")))
                except ValueError:
                    pass
    nb = _nama_item_bersih(nama_item) if nama_item else ""

    def _judul_item(ket: str) -> bool:
        """True bila ket adalah judul/kode item (mengandung nama item)."""
        if not nb or len(nb) < 5:
            return False
        kb = re.sub(r"[^a-z0-9]+", "", ket.lower())
        kb = re.sub(r"\d+", "", kb)  # '13 rempela hati' == 'rempela hati'
        return bool(kb) and len(kb) >= 4 and (kb in nb or nb in kb)

    def _ket_valid(ket: str) -> bool:
        ket2 = ket.strip(" -–—")
        if len(ket2) < 3 or re.search(r"\d", ket2):
            return False
        if ket2.lower() in ("c", "a", "b", "d", "e", "nasi", "ayam"):
            return False
        if _judul_item(ket2):
            return False
        return True

    opsi = []
    gantung = []           # antrian label huruf yang barisnya terpisah ("A.", "B.")
    kandidat_satuan = []   # kategori A-D: "1 Piring Bayi", "1 Mangkok Kecil"...
    kandidat_desc = []     # kategori A-D: "Porsi Besar", "Mangkuk Kecil"...
    for b in baris:
        if gantung:
            # baris berikut yang valid menjadi ket untuk label pertama antrian
            if _REG_SATUAN_OPT.match(b) or _ket_valid(b):
                if not _judul_item(b):
                    opsi.append({"label": gantung.pop(0), "ket": b, "gram": None})
                    continue
            gantung.clear()
        if len(b) <= 2 and b.isalpha():
            continue  # huruf lepas (label di dalam foto) — tak bisa dipasang
        # judul/kode item hanya diskip bila belum ada opsi; setelah ada opsi,
        # pola "D.5 ptg dadu" adalah opsi foto lanjutan, bukan kode item
        if (not opsi) and (_REG_KODE_ITEM.match(b) or _REG_KODE_ITEM2.match(b)):
            continue
        m = _REG_OPT.match(b)
        if m:
            ket = m.group(2).strip()
            if not _judul_item(ket):
                opsi.append({"label": m.group(1).upper(), "ket": ket, "gram": None})
            continue
        m2 = _REG_OPT2.match(b)
        if m2:
            ket = b[m2.end():].strip()
            if not _judul_item(ket):
                opsi.append({"label": m2.group(1).upper(), "ket": ket, "gram": None})
            continue
        mg = re.match(r"^([A-Za-z])\.\s*$", b)
        if mg:
            gantung.append(mg.group(1).upper())  # label menggantung, ket di baris berikut
            continue
        if kategori in ("A", "B", "C", "D"):
            if _REG_SATUAN_OPT.match(b) and _ket_valid(b):
                kandidat_satuan.append(b)
            elif _ket_valid(b) and re.search(r"[a-z]{3,}", b, re.IGNORECASE):
                kandidat_desc.append(b)
    # opsi tunggal (semua kategori): "1 bh" + 1 angka (kue/jajanan/telur)
    if not opsi and len(angka) == 1:
        for b in baris:
            if _REG_SATUAN_OPT.match(b):
                ket = b
                if not _judul_item(ket):
                    opsi.append({"label": "-", "ket": ket, "gram": None})
                    break
    # isi dari kandidat (kategori A-D): satuan beruntun dulu, baru deskripsi
    if not opsi and kategori in ("A", "B", "C", "D"):
        src = kandidat_satuan or kandidat_desc
        for b in src:
            opsi.append({"label": chr(ord("A") + len(opsi)), "ket": b, "gram": None})
            if len(opsi) >= max(len(angka), 1) or len(opsi) >= 6:
                break
    # cocokkan angka berurutan ke opsi
    if opsi and angka:
        for i, o in enumerate(opsi):
            if i < len(angka):
                o["gram"] = angka[i]
    return opsi


def _nama_item_bersih(nama: str) -> str:
    """Nama item tanpa kode & keterangan: 'A1. Nasi Putih (Piring)' -> 'nasiputih'."""
    n = re.sub(r"^[A-Z]\.?\d+\s*\.?\s*", "", nama, flags=re.IGNORECASE)
    n = re.sub(r"\([^)]*\)", "", n)
    return re.sub(r"[^a-z0-9]+", "", n.lower())


def _buang_footer(nama_item: str, porsi: list[dict]) -> list[dict]:
    """Buang opsi gram=None yang sebenarnya footer/nama item (OCR terpotong)."""
    if not porsi:
        return porsi
    from difflib import SequenceMatcher
    nb = _nama_item_bersih(nama_item)
    if len(nb) < 5:
        return porsi
    out = []
    for o in porsi:
        if o.get("gram") is not None:
            out.append(o)
            continue
        kb = re.sub(r"[^a-z0-9]+", "", o["ket"].lower())
        if not kb:
            continue
        mirip = (nb.startswith(kb) or kb.startswith(nb) or kb in nb or nb in kb
                 or SequenceMatcher(None, kb, nb).ratio() > 0.85)
        if mirip and len(kb) >= 6:
            continue  # footer mirip nama item -> buang
        out.append(o)
    return out


# Koreksi manual hasil OCR (kode -> porsi override). Dipakai untuk halaman
# yang OCR-nya rusak / formatnya komponen (minuman) — foto tetap ditampilkan,
# gram diisi dari keterangan yang terbaca jelas.
# "porsi": [] artinya tampilkan foto saja (format komponen, bukan porsi foto).
KOREKSI_MANUAL: dict[str, dict] = {
    # Bakso Rebus: angka tengah (1 bh sedang) tak terbaca OCR
    "bf_046": {"porsi": [
        {"label": "A", "ket": "1 bh besar", "gram": 90.0},
        {"label": "B", "ket": "1 bh sedang", "gram": None},
        {"label": "C", "ket": "1 bh kecil", "gram": 15.0},
    ]},
    # Rempela Hati: label antrian OCR kacau; angka 15 & 30 terbaca jelas
    "bf_053": {"porsi": [
        {"label": "A", "ket": "1 pt Rempela", "gram": 15.0},
        {"label": "B", "ket": "1 pt Hati", "gram": 30.0},
        {"label": "C", "ket": "1 pt Jantung", "gram": None},
    ]},
    # Gulai Daun Singkong: OCR halaman rusak -> foto saja
    "bf_117": {"porsi": []},
    # Minuman: halaman memuat KOMPOSISI per gelas (bukan pilihan porsi foto)
    "bf_237": {"porsi": []},  # G3 Kopi Susu
    "bf_238": {"porsi": []},  # G4 Susu
    "bf_239": {"porsi": []},  # G5 Kopi 1 Cangkir
    # G6 Susu Cair: label 'R' terbaca salah (harusnya A '1 Gelas')
    "bf_240": {"porsi": [
        {"label": "A", "ket": "1 Gelas", "gram": 200.0},
        {"label": "B", "ket": "1 Kotak Besar", "gram": 200.0},
        {"label": "C", "ket": "1 Kotak Kecil", "gram": 125.0},
    ]},
    # Pepaya & Semangka: OCR halaman rusak parah -> foto saja
    "bf_154": {"porsi": []},  # D.27 Pepaya
    "bf_163": {"porsi": []},  # D.38 Semangka
}


def bangun_katalog_urt() -> list[dict]:
    """Parse SEMUA halaman OCR -> [{kode, nama, kategori, foto, porsi:[...]}].

    Hanya item yang OCR-nya menghasilkan minimal 1 porsi yang disertakan
    dengan porsi terisi; item lain tetap muncul dgn porsi [].
    """
    out = []
    for it in muat_daftar():
        # hanya item makanan resmi buku (kode A1., B.9, ..., G6.) — buang
        # halaman alat makan / URT / contoh yang ikut terbaca di TOC
        if not re.match(r"^[A-G]\.?\s?\d", it["nama"]):
            continue
        if it["kode"] in KOREKSI_MANUAL:
            porsi = KOREKSI_MANUAL[it["kode"]]["porsi"]
        else:
            porsi = parse_ocr_ke_porsi(
                _teks_ocr(it["kode"]), kategori=it.get("kategori", ""), nama_item=it["nama"]
            )
            porsi = _buang_footer(it["nama"], porsi)
        it2 = dict(it)
        it2["nama"] = re.sub(r"^[A-G]\.?\s?\d+\.?\s*", "", it["nama"]).strip()
        it2["kategori"] = it["nama"][0].upper()
        it2["porsi"] = porsi
        out.append(it2)
    return out


def muat_katalog_urt() -> list[dict]:
    """Katalog URT siap pakai (dari JSON cache; bangun ulang bila belum ada)."""
    if URT_FILE.exists():
        try:
            return json.loads(URT_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    data = bangun_katalog_urt()
    try:
        URT_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001
        pass
    return data


def cari_item(katalog: list[dict], teks: str, limit: int = 6) -> list[dict]:
    """Cari item buku foto yang cocok dengan teks (nama item)."""
    if not katalog or not teks:
        return []
    t = teks.lower().strip()
    token = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 3]
    if not token:
        return []
    skor = []
    for it in katalog:
        nl = it["nama"].lower()
        s = 0
        if nl == t:
            s += 200
        elif nl.startswith(t):
            s += 60
        if all(w in nl for w in token):
            s += 50
        for i, w in enumerate(token):
            if w in _KATA_UMUM:
                bobot = 3 if i == 0 else 2
            else:
                bobot = 15 if i == 0 else 8
            if w in nl:
                s += bobot
        if s > 0:
            skor.append((s, it))
    skor.sort(key=lambda x: -x[0])  # stabil: skor sama -> urutan buku (halaman)
    return [it for _, it in skor[:limit]]


def cari_porsi(katalog: list[dict], istilah: str):
    """Item buku foto pertama yang cocok dgn istilah DAN punya porsi ber-gram.

    Dipakai untuk menyambungkan hasil AI ke pilihan porsi dari buku foto.
    """
    for it in cari_item(katalog, istilah, limit=3):
        if any(p.get("gram") is not None for p in it.get("porsi", [])):
            return it
    return None


def kumpul_porsi(katalog: list[dict], istilah: str, max_item: int = 3,
                 max_porsi: int = 4) -> list[dict]:
    """Kumpulkan porsi ber-gram dari beberapa item buku foto yang cocok.

    Dipakai tab AI: 'nasi 1 centong' -> pilihan dari Nasi Putih (Piring),
    Nasi Putih (Centong&Sendok), Nasi Tim, ... biar pasien pilih yang sesuai.
    """
    out = []
    for it in cari_item(katalog, istilah, limit=max_item):
        for p in it.get("porsi", []):
            if p.get("gram") is not None:
                out.append({
                    "kode": it["kode"],
                    "nama": it["nama"],
                    "label": p["label"],
                    "ket": p["ket"],
                    "gram": float(p["gram"]),
                })
        if len(out) >= max_porsi * 2:
            break
    return out


def cari_bahan_tkpi_dari_nama(nama_buku: str):
    """Nama item buku foto -> istilah pencarian TKPI (buang keterangan foto)."""
    nama_buku = re.sub(r"\s*\((piring|centong[^)]*|sendok[^)]*)\)\s*$", "", nama_buku,
                       flags=re.IGNORECASE)
    nama_buku = re.sub(r"\s*\([^)]*\)\s*$", "", nama_buku).strip()
    return nama_buku
