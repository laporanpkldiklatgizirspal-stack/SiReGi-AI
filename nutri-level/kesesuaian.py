"""
GiziLens — cek KELAYAKAN produk untuk kondisi pengguna ("layak untukku?").

Sederhana & transparan: setiap kondisi punya satu zat yang diperhatikan, dengan dua
ambang (batas aman per sajian & batas "sebaiknya dihindari"). Huruf Nutri-Level
(dari aturan Kemenkes) ikut dipakai sebagai penguat: level C/D menjadikan produk
minimal "batasi".

Semua angka di sini adalah **acuan edukasi**, bukan diagnosis. Nilai bisa disesuaikan
di config.py (KONDISI_ATURAN).
"""

from __future__ import annotations

KONDISI_ATURAN = {
    "diabetes": {
        "nama": "Diabetes / gula darah tinggi",
        "zat": "gula", "satuan": "g", "emoji": "🩸",
        "aman": 5.0,       # <= 5 g gula per sajian  -> masih layak
        "batasi": 15.0,    # <= 15 g                 -> layak sesekali / batasi porsi
        "saran": "Pilih produk bergula rendah, dan hitung gula harian tetap ≤ 50 g.",
    },
    "hipertensi": {
        "nama": "Hipertensi / tekanan darah tinggi",
        "zat": "natrium", "satuan": "mg", "emoji": "💗",
        "aman": 120.0,     # <= 120 mg natrium per sajian
        "batasi": 500.0,   # <= 500 mg
        "saran": "Batasi natrium ≤ 2.000 mg/hari (± 1 sendok teh garam).",
    },
    "kolesterol": {
        "nama": "Kolesterol tinggi",
        "zat": "lemak_jenuh", "satuan": "g", "emoji": "🫀",
        "aman": 1.5,       # <= 1,5 g lemak jenuh per sajian
        "batasi": 5.0,     # <= 5 g
        "saran": "Kurangi lemak jenuh & gorengan; utamakan lemak tak jenuh.",
    },
    "asam_urat": {
        "nama": "Asam urat / gout",
        "zat": "gula", "satuan": "g", "emoji": "🦶",
        "aman": 10.0,
        "batasi": 25.0,
        "saran": "Batasi minuman manis (fruktosa) & perhatikan asupan cairan.",
    },
}

VERDICT_URUT = ["layak", "batasi", "hindari"]
VERDICT_INFO = {
    "layak": ("🟢 LAYAK", "Aman untuk kondisimu", "#16A34A", "#E8F9EF"),
    "batasi": ("🟡 BATASI", "Boleh, tapi jangan sering / kecilkan porsi", "#D97706", "#FEF3E2"),
    "hindari": ("🔴 TIDAK DISARANKAN", "Sebaiknya pilih produk lain", "#DC2626", "#FDECEC"),
}
NUTRISI_NAMA = {"gula": "gula", "natrium": "natrium", "lemak_jenuh": "lemak jenuh",
                "lemak": "lemak total"}


def nama_kondisi(kunci: str) -> str:
    return KONDISI_ATURAN.get(kunci, {}).get("nama", kunci)


def _nilai_zat(per_sajian: dict, zat: str):
    """Ambil nilai zat dari data per sajian (lemak jenuh diambil dari 'lemak_jenuh')."""
    v = (per_sajian or {}).get(zat)
    if v is None and zat == "lemak_jenuh":
        v = (per_sajian or {}).get("lemak_jenuh")
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def verdict_zat(nilai: float | None, aturan_zat: dict, level_nl: str | None = None) -> str:
    """Tentukan verdict satu zat: layak / batasi / hindari."""
    if nilai is None:
        dasar = "layak"
    elif nilai <= aturan_zat["aman"]:
        dasar = "layak"
    elif nilai <= aturan_zat["batasi"]:
        dasar = "batasi"
    else:
        dasar = "hindari"
    # huruf Nutri-Level ikut menguatkan (C/D minimal 'batasi', D + nilai tinggi tetap hindari)
    if level_nl in ("C", "D") and VERDICT_URUT.index(dasar) < VERDICT_URUT.index("batasi"):
        dasar = "batasi"
    if level_nl == "D" and nilai is not None and nilai > aturan_zat["batasi"]:
        dasar = "hindari"
    return dasar


def cek_kelayakan(per_sajian: dict, kondisi: list | None = None,
                  level_nutri_level: dict | None = None) -> dict:
    """Hasil kelayakan produk untuk pengguna.

    per_sajian        : {"gula": .., "natrium": .., "lemak": .., "lemak_jenuh": ..}
    kondisi           : daftar kunci kondisi (["diabetes", ...])
    level_nutri_level : {"gula": "A".."D", "natrium": .., "lemak_jenuh": ..} (opsional)

    Return {verdict, badge, pesan, warna, latar, alasan:[...], kondisi_kosong:bool}
    """
    kondisi = [k for k in (kondisi or []) if k in KONDISI_ATURAN]
    level_nutri_level = level_nutri_level or {}
    if not kondisi:
        return {"verdict": None, "badge": "ℹ️ BELUM ADA PROFIL",
                "pesan": "Isi Profil Saya dulu supaya aplikasi bisa menilai kelayakan produk untukmu.",
                "warna": "#1565C0", "latar": "#EAF1FB", "alasan": [], "kondisi_kosong": True,
                "butuh_profil": True}

    alasan, verdicts = [], []
    for kunci in kondisi:
        atur = KONDISI_ATURAN[kunci]
        nilai = _nilai_zat(per_sajian, atur["zat"])
        v = verdict_zat(nilai, atur, (level_nutri_level or {}).get(atur["zat"]))
        verdicts.append(v)
        nilai_teks = "belum ada angkanya" if nilai is None else f"{nilai:g} {atur['satuan']}"
        alasan.append({
            "kondisi": atur["nama"],
            "emoji": atur["emoji"],
            "zat": NUTRISI_NAMA.get(atur["zat"], atur["zat"]),
            "nilai": nilai,
            "nilai_teks": nilai_teks,
            "verdict": v,
            "badge": VERDICT_INFO[v][0],
            "saran": atur["saran"],
        })

    terburuk = max(verdicts, key=lambda v: VERDICT_URUT.index(v)) if verdicts else "layak"
    badge, pesan, warna, latar = VERDICT_INFO[terburuk]
    return {
        "verdict": terburuk,
        "badge": badge,
        "pesan": pesan,
        "warna": warna,
        "latar": latar,
        "alasan": alasan,
        "kondisi_kosong": False,
        "butuh_profil": False,
    }
