# -*- coding: utf-8 -*-
"""AI Recall offline (rule-based, tanpa internet/API).

Mengubah teks bahasa sehari-hari pasien menjadi item recall:
  1. Mengenali makanan dari teks        -> pecah kalimat jadi item
  2. Interpretasi bahasa sehari-hari    -> "setengah piring", "sepotong" dsb
  3. Estimasi berat makanan             -> satuan rumah tangga -> gram
  4. Pencocokan database makanan        -> cari kandidat bahan di TKPI
Diproses 100% lokal; hasilnya selalu bisa diperiksa & diedit ahli gizi.
"""
from __future__ import annotations

import re

import pandas as pd

KATEGORI_WAKTU = ["Pagi", "Siang", "Malam", "Selingan"]

# Urutan deteksi penanda waktu makan (regex -> kategori)
POLA_WAKTU = [
    (r"\b(makan\s+malam|makanmalam|malam)\b", "Malam"),
    (r"\b(makan\s+siang|makansiang|siang)\b", "Siang"),
    (r"\b(sarapan|makan\s+pagi|makanspagi|pagi)\b", "Pagi"),
    (r"\b(selingan|snack|cemilan|kudapan|ngemil)\b", "Selingan"),
]

# Satuan rumah tangga -> gram (estimasi umum; tetap bisa diedit user)
SATUAN_GRAM = {
    "centong": 100.0,
    "piring": 100.0,
    "mangkok": 100.0,
    "mangkuk": 100.0,
    "gelas": 200.0,
    "potong": 50.0,
    "buah": 50.0,
    "butir": 50.0,
    "iris": 10.0,
    "lembar": 10.0,
    "sendok": 10.0,
    "sdm": 10.0,
    "sdt": 5.0,
    "porsi": 100.0,
    "bungkus": 50.0,
    "ekor": 50.0,
    "kepal": 50.0,
    "genggam": 25.0,
    "kecil": 50.0,
    "sedang": 100.0,
    "besar": 150.0,
}

# Kata bilangan -> angka
KATA_ANGKA = {
    "tiga perempat": 0.75,
    "setengah": 0.5,
    "seperempat": 0.25,
    "satu": 1.0,
    "dua": 2.0,
    "tiga": 3.0,
    "empat": 4.0,
    "lima": 5.0,
    "enam": 6.0,
    "tujuh": 7.0,
    "delapan": 8.0,
    "sembilan": 9.0,
    "sepuluh": 10.0,
}

# Awalan "se-"+satuan = 1 satuan (sepotong=1 potong, segelas=1 gelas, ...)
SE_SATUAN = {
    "potong", "buah", "gelas", "butir", "iris", "lembar", "porsi", "ekor",
    "mangkok", "mangkuk", "piring", "centong", "sendok", "cangkir", "genggam",
}

# Kata sambung/pengisi yang dibuang saat mencari nama bahan
KATA_BUANG = {
    "makan", "minum", "dan", "sama", "plus", "dengan", "nya", "yang", "lalu",
    "kemudian", "terus", "ada", "saya", "aku", "tadi", "juga", "sudah",
    "habis", "waktu", "jam", "pukul", "kurang", "lebih", "setengah",
}

# Kata GENERIK nama bahan (kategori/cara masak) — berbobot kecil saat
# pencocokan supaya kata spesifik (mis. 'bayam') yang menentukan hasil.
KATA_UMUM_BAHAN = {
    "sayur", "buah", "ikan", "ayam", "daging", "sapi", "kambing", "kerbau",
    "nasi", "telur", "goreng", "rebus", "bakar", "panggang", "kukus", "tumis",
    "kuah", "santan", "masakan", "masak", "segar", "kering", "mentah",
    "matang", "muda", "tua", "besar", "kecil", "manis", "asin", "tawar",
    "dadar", "bumbu", "olahan", "campur", "santan", "siap", "santap",
}

_DAFTAR_SATUAN = "|".join(sorted(SATUAN_GRAM.keys(), key=len, reverse=True))
_REG_SATUAN = re.compile(rf"\b({_DAFTAR_SATUAN})\b", re.IGNORECASE)
_REG_ANGKA = re.compile(r"(\d+(?:[.,]\d+)?)")
_REG_PECAHAN = re.compile(r"(\d+)\s*/\s*(\d+)")


def _bersihkan(teks: str) -> str:
    return re.sub(r"\s+", " ", teks.replace("\n", " ")).strip()


def _pecah_waktu(teks: str):
    """Pecah teks jadi [(kategori_waktu, isi_teks)].

    Teks tanpa penanda waktu -> satu segmen dengan kategori kosong (""),
    nanti di UI bisa dipilih kategorinya.
    """
    low = teks.lower()
    temuan = []  # (posisi, kategori)
    for pola, kat in POLA_WAKTU:
        for m in re.finditer(pola, low):
            # hindari kata 'pagi/siang/malam' sebagai bagian kata lain
            temuan.append((m.start(), kat, m.end()))
    if not temuan:
        return [("", teks)]
    temuan.sort(key=lambda x: x[0])
    segmen = []
    # teks sebelum penanda pertama dianggap milik segmen pertama
    awal = teks[: temuan[0][0]]
    for i, (pos, kat, end) in enumerate(temuan):
        if i + 1 < len(temuan):
            isi = teks[end: temuan[i + 1][0]]
        else:
            isi = teks[end:]
        isi = _bersihkan((awal if i == 0 else "") + " " + isi)
        awal = ""
        segmen.append((kat, isi))
    return segmen


def _pecah_item(isi: str):
    """Pisahkan satu segmen waktu jadi frasa item (koma / 'dan')."""
    s = re.sub(r"\b(dan|sama|plus|lalu|kemudian)\b", ",", isi, flags=re.IGNORECASE)
    s = re.sub(r"[,;]+", ",", s)
    out = []
    for frasa in s.split(","):
        frasa = frasa.strip().strip(".,;:!?()\"'").strip()
        if not frasa:
            continue
        # buang frasa yang hanya kata sambung/pengisi
        kata = [w for w in re.findall(r"[a-zA-Z0-9]+", frasa.lower()) if w not in KATA_BUANG]
        if not kata:
            continue
        out.append(frasa)
    return out


def _ekstrak_porsi(frasa: str):
    """Kembalikan (jumlah, satuan, istilah_bahan).

    Contoh: 'nasi 1 centong'   -> (1, 'centong', 'nasi')
            'setengah piring nasi' -> (0.5, 'piring', 'nasi')
            'telur dadar'      -> (1, '', 'telur dadar')
    """
    f = frasa.strip()
    low = f.lower()
    jumlah = 1.0
    satuan = ""

    # 1) pecahan "1/2", "1/4" di mana pun
    m = _REG_PECAHAN.search(low)
    if m:
        try:
            jumlah = float(m.group(1)) / float(m.group(2))
            f = (f[: m.start()] + " " + f[m.end():]).strip()
            low = f.lower()
        except ZeroDivisionError:
            pass

    # 2) pola "ANGKA + satuan" (mis. '1 centong', '2 potong', '0,5 gelas')
    m = re.search(rf"(\d+(?:[.,]\d+)?)\s*({_DAFTAR_SATUAN})\b", low)
    if m:
        try:
            jumlah = float(m.group(1).replace(",", "."))
        except ValueError:
            pass
        satuan = m.group(2).lower()
        f = (f[: m.start()] + " " + f[m.end():]).strip()
        low = f.lower()

    # 3) kata bilangan di awal ("setengah piring", "dua potong", "sepotong"...)
    if not m:
        # 3a) awalan "se-"+satuan = 1 satuan
        mse = re.match(rf"\bse({_DAFTAR_SATUAN})\b", low)
        if mse:
            jumlah = 1.0
            satuan = mse.group(1).lower()
            f = f[mse.end():].strip()
            low = f.lower()
        else:
            for kata in sorted(KATA_ANGKA.keys(), key=len, reverse=True):
                if low.startswith(kata + " ") or low == kata:
                    jumlah = KATA_ANGKA[kata]
                    f = f[len(kata):].strip()
                    low = f.lower()
                    # cari satuan yang mengikuti kata bilangan
                    m2 = _REG_SATUAN.search(f)
                    if m2:
                        satuan = m2.group(1).lower()
                        f = (f[: m2.start()] + " " + f[m2.end():]).strip()
                        low = f.lower()
                    break

    # 4) kalau belum dapat satuan, cari satuan di mana pun ("nasi centong")
    if not satuan:
        m = _REG_SATUAN.search(f)
        if m:
            satuan = m.group(1).lower()
            f = (f[: m.start()] + " " + f[m.end():]).strip()

    # 5) angka tersisa di awal tanpa satuan ("2 telur", "telur 2")
    if jumlah == 1.0 and satuan == "":
        m = re.match(r"(\d+(?:[.,]\d+)?)\b\s*", low)
        if m:
            try:
                jumlah = float(m.group(1).replace(",", "."))
            except ValueError:
                pass
            f = f[m.end():].strip()
        else:
            m = re.search(r"\s(\d+(?:[.,]\d+)?)\s*$", low)
            if m:
                try:
                    jumlah = float(m.group(1).replace(",", "."))
                except ValueError:
                    pass
                f = (f[: m.start()] + " " + f[m.end():]).strip()

    # 6) buang sisa angka & tanda baca, rapikan
    f = re.sub(r"\d+(?:[.,]\d+)?", " ", f)
    f = re.sub(r"[.,;:()\"']", " ", f)
    f = re.sub(r"\bse(potong|buah|gelas|butir|iris|lembar|porsi|ekor|mangkok|mangkuk|piring|centong|sendok)\b", " ", f, flags=re.IGNORECASE)
    f = _bersihkan(f)
    kata = [w for w in f.split() if w.lower() not in KATA_BUANG]
    istilah = " ".join(kata).strip(" -–—")
    if not istilah:
        istilah = frasa.strip()
    return jumlah, satuan, istilah


def _estimasi_gram(jumlah: float, satuan: str, istilah: str) -> float | None:
    """Estimasi gram dari satuan rumah tangga; None bila tak bisa diperkirakan."""
    g = SATUAN_GRAM.get(satuan)
    if g is not None:
        return round(jumlah * g, 1)
    # tanpa satuan tapi ada jumlah -> asumsi 1 porsi umum 100 g
    if not satuan:
        return round(jumlah * 100.0, 1)
    return None


def cari_kandidat(tkpi: pd.DataFrame, istilah: str, limit: int = 8):
    """Cari bahan di TKPI yang paling cocok dengan istilah (skor sederhana).

    Mengembalikan list nama bahan teratas; kosong bila tidak ada yang cocok.
    Prioritas: nama sama persis > nama diawali istilah > istilah muncul utuh
    sebagai kata > kemiripan token (token pertama lebih berbobot).

    Kata GENERIK (sayur, buah, ikan, goreng, rebus, ...) sengaja diberi bobot
    kecil supaya tidak menenggelamkan kata spesifik: 'sayur bayam' harus
    cocok ke 'Bayam, segar', bukan ke 'Sayur asem'.
    """
    if tkpi is None or tkpi.empty or not istilah:
        return []
    nama_col = "Nama Bahan Makanan"
    if nama_col not in tkpi.columns:
        return []
    ist = istilah.lower().strip()
    token = [w for w in re.findall(r"[a-z0-9]+", ist) if len(w) >= 3 and w not in KATA_BUANG]
    if not token:
        return []
    generik = KATA_UMUM_BAHAN
    pola_utuh = re.compile(rf"\b{re.escape(ist)}\b")
    skor = []
    for nama in tkpi[nama_col].astype(str):
        nl = nama.lower().strip()
        s = 0
        if nl == ist:
            s += 200
        elif nl.startswith(ist):
            s += 60
        if pola_utuh.search(nl):
            s += 100
        for i, w in enumerate(token):
            if w in generik:
                bobot = 6 if i == 0 else 3
            else:
                bobot = 30 if i == 0 else 12
            if re.search(rf"\b{re.escape(w)}\b", nl):
                s += bobot
        # nama yang DIAWALI kata kunci SPESIFIK jauh lebih relevan
        # (mis. 'sayur bayam' -> 'Bayam, segar', bukan 'Ikan Teri nasi, ...')
        if token and token[0] not in generik and nl.startswith(token[0]):
            s += 45
        if s > 0:
            skor.append((s, nama))
    skor.sort(key=lambda x: (-x[0], x[1].lower()))
    return [n for _, n in skor[:limit]]


def parse_recall(teks: str, tkpi: pd.DataFrame | None = None) -> list[dict]:
    """Ubah teks bebas menjadi daftar item recall mentah.

    Tiap item: dict(waktu, istilah, jumlah, satuan, gram, kandidat, perlu_cek)
    """
    teks = _bersihkan(teks)
    if not teks:
        return []
    hasil = []
    for kat, isi in _pecah_waktu(teks):
        for frasa in _pecah_item(isi):
            jumlah, satuan, istilah = _ekstrak_porsi(frasa)
            if not istilah:
                continue
            gram = _estimasi_gram(jumlah, satuan, istilah)
            kandidat = cari_kandidat(tkpi, istilah)
            hasil.append({
                "waktu": kat,
                "istilah": istilah,
                "jumlah": jumlah,
                "satuan": satuan,
                "gram": gram,
                "kandidat": kandidat,
                "perlu_cek": not kandidat or gram is None,
            })
    return hasil


def ringkasan_cepat(hasil: list[dict]) -> str:
    """Ringkasan satu-dua kalimat dari hasil pengenalan (fungsi 9 sederhana)."""
    if not hasil:
        return "Tidak ada makanan yang dikenali."
    n = len(hasil)
    waktu_terlibat = sorted({h["waktu"] for h in hasil if h["waktu"]})
    butuh_cek = sum(1 for h in hasil if h.get("perlu_cek"))
    kal = f"Dikenali {n} item makanan"
    if waktu_terlibat:
        kal += " (" + ", ".join(waktu_terlibat) + ")"
    kal += "."
    if butuh_cek:
        kal += f" {butuh_cek} item perlu pemeriksaan manual (bahan/gram belum pasti)."
    else:
        kal += " Semua item sudah diperkirakan gramnya dari satuan rumah tangga."
    return kal
