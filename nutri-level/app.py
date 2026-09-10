"""
GiziLens — Pemindai Label GGL + Tracker GGL Harian.

Alur utama:
📷 Scan label -> 🤖 AI/OCR baca GGL -> 🔎 Konfirmasi hasil (bisa diedit)
-> 🍽️ Pilih jumlah sajian dikonsumsi -> 📊 Lihat dampak ke total hari ini
-> ➕ Tambahkan ke GGL Hari Ini -> 💾 SQLite -> 🟢🟡🔴 dashboard ter-update.

Jalankan:  streamlit run app.py
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd
import streamlit as st

import config
import database as db
import nutri_level as nl
import pengaturan as setel
import nutrition_tracker as tracker
import nutrition_ui as ui
from nutrition_calculator import badge, dampak_penambahan, nilai_dikonsumsi, ringkas_garam, ringkas_zat
from nutrition_reader import kunci_gemini_dari_secrets, nama_default_produk, read_label
from utils import (fmt_jumlah, fmt_persen, now_time, parse_float,
                   salt_gram, tanggal_id, today_iso)

db.init_database()

st.set_page_config(
    page_title="GiziLens — Tracker GGL Harian",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(ui.css() + ui.css_nutri_level() + ui.css_desain_a(), unsafe_allow_html=True)

NAV = [
    "🏠 Beranda",
    "📷 Scan Produk",
    "📊 GGL Hari Ini",
    "📅 Riwayat",
    "📈 Ringkasan",
    "📖 Edukasi",
    "⚙️ Pengaturan",
    "ℹ️ Tentang",
]

# ---------------------------------------------------------------------------
# State bantu
# ---------------------------------------------------------------------------
def ss(k, v):
    if k not in st.session_state:
        st.session_state[k] = v


ss("nav", NAV[0])
ss("stage_scan", "kamera")   # kamera | konfirmasi
ss("scan", None)
ss("added_ok", False)
ss("nama_produk", "")
ss("hist_date", _dt.date.today())


def reset_scan():
    for k in ("scan", "added_ok", "nama_produk", "takaran_saji",
              "sajian_kemasan", "inp_gula", "inp_natrium", "inp_lemak"):
        st.session_state.pop(k, None)
    st.session_state.stage_scan = "kamera"


def sidebar():
    with st.sidebar:
        st.markdown(f"## 🔵 **{config.APP_NAME}**")
        st.caption(config.ORG)
        pilihan = st.radio("Menu", NAV, index=NAV.index(st.session_state.nav),
                           label_visibility="collapsed")
        st.session_state.nav = pilihan
        if db.lokasi_db_cadangan():
            st.caption("⚠️ DB sementara (folder temp) — data bisa hilang saat server mati.")
        st.markdown("---")
        st.caption(f"📅 {tanggal_id(_dt.date.today())}")


def _kartu_3(html_list: list[str]):
    kolom = st.columns(len(html_list))
    for k, h in zip(kolom, html_list):
        k.markdown(h, unsafe_allow_html=True)


# ===========================================================================
# ⚙️ PENGATURAN
# ===========================================================================
def halaman_pengaturan():
    ui.judul_seksi("⚙️ Pengaturan", "Isi ambang Nutri-Level & lihat batas harian yang dipakai.")
    d = setel.muat()

    st.markdown("#### 🍽️ Batas konsumsi harian (GGL)")
    st.markdown(
        f"- 🍬 **Gula {fmt_jumlah(config.DAILY_LIMITS['sugar_g'])} g** per hari (± 4 sendok makan)\n"
        f"- 🧂 **Natrium {fmt_jumlah(config.DAILY_LIMITS['sodium_mg'])} mg** per hari "
        "(± 1 sendok teh garam / 5 g)\n"
        f"- 🥑 **Lemak {fmt_jumlah(config.DAILY_LIMITS['fat_g'])} g** per hari (± 5 sendok makan)\n"
        "- Ambang warna: 🟢 < 50% · 🟡 50–99% · 🔴 ≥ 100% dari batas harian."
    )
    st.caption("Dasar: Permenkes RI No. 30 Tahun 2013 & rekomendasi WHO. Angka ini dipakai untuk "
               "'Cek Kebutuhan Harianku' di halaman Scan.")

    st.markdown("---")
    st.markdown("#### 🏷️ Ambang Nutri-Level (label depan kemasan Kemenkes)")
    st.caption("Format: batas **A** · batas **B** · batas **C**. Contoh: A ≤ batas A, B ≤ batas B, "
               "C ≤ batas C, D lebih dari batas C.")

    def _baris_ambang(prefix: str, label: str, nilai: list, maks: float, step: float, bantuan: str = "") -> list:
        kol = st.columns([2.4, 1, 1, 1])
        kol[0].markdown(f"**{label}**")
        a = kol[1].number_input("A ≤", 0.0, maks, float(nilai[0]), step, key=f"{prefix}_a", help=bantuan)
        b = kol[2].number_input("B ≤", 0.0, maks, float(nilai[1]), step, key=f"{prefix}_b")
        c = kol[3].number_input("C ≤", 0.0, maks, float(nilai[2]), step, key=f"{prefix}_c")
        return [a, b, c]

    st.markdown("**🥤 Minuman (per 100 mL)** — sesuai poster Kemenkes")
    minum = {
        "gula": _baris_ambang("nlmin_gula", "🍬 Gula (g/100 mL)",
                              d["ambang_minuman"].get("gula", [1.0, 5.0, 10.0]), 100.0, 0.5),
        "natrium": _baris_ambang("nlmin_na", "🧂 Garam/natrium (mg/100 mL)",
                                 d["ambang_minuman"].get("natrium", [5.0, 120.0, 500.0]), 5000.0, 5.0),
        "lemak_jenuh": _baris_ambang("nlmin_lj", "🥑 Lemak jenuh (g/100 mL)",
                                     d["ambang_minuman"].get("lemak_jenuh", [0.7, 1.2, 2.8]), 50.0, 0.1),
    }

    st.markdown("**🍪 Makanan (per 100 g)** — isi sesuai poster/aturan resmi")
    if not d["ambang_makanan"]:
        st.info("⚠️ Masih kosong — artinya aplikasi belum bisa memberi huruf Nutri-Level untuk produk "
                "makanan (biskuit, mie, snack, dll). Isi angkanya di bawah sesuai poster Kemenkes versi "
                "makanan, lalu tekan **Simpan**.")
    mkanan = {
        "gula": _baris_ambang("nlmkn_gula", "🍬 Gula (g/100 g)",
                              d["ambang_makanan"].get("gula", [0.0, 0.0, 0.0]), 100.0, 0.5),
        "natrium": _baris_ambang("nlmkn_na", "🧂 Garam/natrium (mg/100 g)",
                                 d["ambang_makanan"].get("natrium", [0.0, 0.0, 0.0]), 5000.0, 5.0),
        "lemak_jenuh": _baris_ambang("nlmkn_lj", "🥑 Lemak jenuh (g/100 g)",
                                     d["ambang_makanan"].get("lemak_jenuh", [0.0, 0.0, 0.0]), 50.0, 0.1),
    }
    sumber_makanan = st.text_input("Catatan sumber angka makanan (opsional)",
                                   value=d.get("batas_nutri_level_makanan_sumber", ""),
                                   placeholder="contoh: poster Kemenkes versi makanan, per 100 g",
                                   key="nl_sumber_makanan")

    s1, s2 = st.columns([1, 1])
    if s1.button("💾 Simpan pengaturan", type="primary", use_container_width=True):
        baru = setel.muat()
        baru["ambang_minuman"] = {k: v for k, v in minum.items() if v[2] > 0}
        baru["ambang_makanan"] = {k: v for k, v in mkanan.items() if v[2] > 0}
        baru["batas_nutri_level_makanan_sumber"] = sumber_makanan.strip()
        if setel.simpan(baru):
            st.success("Tersimpan ✅ — ambang Nutri-Level diperbarui.")
        else:
            st.error("Gagal menyimpan (folder aplikasi tidak bisa ditulis di server ini).")
        st.rerun()
    if s2.button("↩️ Kembalikan ke bawaan", use_container_width=True):
        setel.simpan(dict(setel.BAWAAN))
        st.success("Kembali ke pengaturan bawaan ↩️")
        st.rerun()

    if setel.lokasi_temp():
        st.caption("⚠️ Pengaturan disimpan di folder sementara server (folder aplikasi read-only).")
    st.caption(f"Sumber: {config.NUTRI_LEVEL_SUMBER}. Bila poster resmi memuat angka berbeda, "
               "angka di halaman ini yang dipakai aplikasi.")


# ===========================================================================
# 🏠 BERANDA
# ===========================================================================
def halaman_beranda():
    ui.hero()
    st.markdown("### Selamat Datang di GiziLens 👋")
    st.markdown(
        "Pantau **Gula, Garam & Lemak (GGL)** dari makanan dan minuman kemasan. "
        "Scan labelnya, catat yang kamu konsumsi, dan lihat sisa batas harianmu."
    )

    r = tracker.ringkasan_tanggal()
    st.markdown("#### GGL HARI INI")
    g = r["ringkasan"]["gula"]
    n = r["ringkasan"]["natrium"]
    l = r["ringkasan"]["lemak"]
    _kartu_3([
        ui.kartu_total("🍬", "GULA", g["konsumsi"], g["batas"], "g", g),
        ui.kartu_total("🧂", "GARAM/NATRIUM", n["konsumsi"], n["batas"], "mg", n,
                       baris_tambahan=[f"≈ {fmt_jumlah(n['garam_g'])} / {fmt_jumlah(n['garam_batas_g'])} g garam"]),
        ui.kartu_total("🥑", "LEMAK TOTAL", l["konsumsi"], l["batas"], "g", l),
    ])

    # lingkaran status hari ini (zat yang paling mendekati batas)
    _pilih = max([("🍬 GULA", g), ("🧂 NATRIUM", n), ("🥑 LEMAK", l)], key=lambda t: t[1]["persen"])
    _rr = _pilih[1]
    st.markdown(ui.donat(
        _rr["persen"], config.COLORS.get(_rr["warna"], "#1565C0"),
        f"STATUS HARI INI · {_pilih[0]}",
        fmt_persen(_rr["persen"]), "% batas harian",
        f"{_rr['badge']} · {_rr['pesan']}",
        f"Zat yang paling mendekati batas harian (konsumsi {fmt_jumlah(_rr['konsumsi'])} / "
        f"{fmt_jumlah(_rr['batas'])}).",
    ), unsafe_allow_html=True)

    st.markdown("---")
    b1, b2 = st.columns([1, 1])
    if b1.button("📷 SCAN PRODUK", type="primary", use_container_width=True):
        st.session_state.nav = "📷 Scan Produk"
        st.rerun()
    if b2.button("📊 Lihat GGL Hari Ini", use_container_width=True):
        st.session_state.nav = "📊 GGL Hari Ini"
        st.rerun()


# ===========================================================================
# 📷 SCAN PRODUK
# ===========================================================================
def _proses_foto(byte_img: bytes):
    st.success("✅ Foto berhasil diambil.")
    with st.spinner("Sedang membaca informasi nilai gizi..."):
        try:
            hasil = read_label(byte_img, gemini_key=kunci_gemini_dari_secrets())
        except Exception as exc:
            hasil = {
                "nama_produk": None, "takaran_saji": None, "sajian_per_kemasan": 1,
                "gula": None, "natrium": None, "lemak": None,
                "protein": None, "karbohidrat": None, "energi": None,
                "_baris": [], "_sumber": "gagal", "_ocr_error": str(exc),
            }
    st.session_state.scan = hasil
    st.session_state.added_ok = False
    st.session_state.stage_scan = "konfirmasi"
    st.session_state.nama_produk = nama_default_produk(hasil)
    st.rerun()


def _blok_kandungan_produk(per_sajian: dict, jumlah_sajian: float):
    """A. PRODUK INI (nilai per sajian) + B. JIKA DIKONSUMSI (dampak)."""
    batas = config.DAILY_LIMITS
    ambang = config.STATUS_THRESHOLDS
    r_g = ringkas_zat(per_sajian["gula"], batas["sugar_g"], ambang)
    r_n = ringkas_garam(per_sajian["natrium"], batas["sodium_mg"], ambang)
    r_l = ringkas_zat(per_sajian["lemak"], batas["fat_g"], ambang)

    st.markdown("##### A. PRODUK INI (kandungan per 1 sajian)")
    _kartu_3([
        ui.kartu_total("🍬", "GULA", r_g["konsumsi"], r_g["batas"], "g", r_g),
        ui.kartu_total("🧂", "NATRIUM", r_n["konsumsi"], r_n["batas"], "mg", r_n,
                       baris_tambahan=[f"≈ {fmt_jumlah(r_n['garam_g'])} g garam"]),
        ui.kartu_total("🥑", "LEMAK", r_l["konsumsi"], r_l["batas"], "g", r_l),
    ])
    st.caption("Level warna produk dihitung per 1 sajian terhadap batas harian — "
               "belum tentu sama dengan kualitas total konsumsimu hari ini.")

    # ---- dampak ----
    dampak = dampak_penambahan(
        db.get_daily_totals(today_iso()), nilai_dikonsumsi(per_sajian, jumlah_sajian), ambang)
    st.markdown(f"##### B. JIKA DIKONSUMSI ({fmt_jumlah(jumlah_sajian)} sajian)")
    garis = []
    for meta in config.NUTRIENTS:
        k = meta["key"]
        d = dampak[k]
        unit = meta["unit"]
        garis.append(
            f"**{meta['emoji']} {meta['jenis']}:** "
            f"{fmt_jumlah(d['sekarang'])} → **{fmt_jumlah(d['prediksi'])} {unit}** "
            f"· {fmt_persen(d['persen_sekarang'])}% → **{fmt_persen(d['persen_prediksi'])}%**"
        )
    st.markdown("<br>".join(garis))

    lewat = {meta["key"]: dampak[meta["key"]] for meta in config.NUTRIENTS
             if dampak[meta["key"]]["warna_prediksi"] == "danger"}
    if lewat:
        rincian = "; ".join(
            f"{config.NUTRIENTS[[m['key'] for m in config.NUTRIENTS].index(k)]['emoji']} "
            f"{d['prediksi']:.0f}/{d['batas']:.0f} "
            f"({fmt_persen(d['persen_prediksi'])}%)"
            for k, d in lewat.items())
        ui.banner_peringatan(
            "⚠️ PERHATIAN",
            f"Jika produk ini ditambahkan, total konsumsi harian akan melebihi batas: "
            f"{rincian}. Tetap boleh dicatat — GiziLens hanya mengingatkan, tidak melarang. 😊",
        )
    return dampak


def halaman_scan():
    ui.judul_seksi("📷 Scan Produk", "Arahkan kamera ke bagian Informasi Nilai Gizi pada kemasan.")

    # ---------------- tahap kamera ----------------
    if st.session_state.stage_scan == "kamera" or st.session_state.scan is None:
        if st.session_state.stage_scan != "kamera":
            reset_scan()
        st.markdown(
            '<div class="panel">Pastikan: • Label terlihat penuh • Tulisan tidak buram '
            "• Cahaya cukup • Kamera tidak terlalu miring<br>"
            "• Kalau kamera sulit fokus: geser pelan mendekat/menjauh (±15–25 cm) sampai tajam</div>",
            unsafe_allow_html=True,
        )
        gambar = st.camera_input("Ambil foto label Informasi Nilai Gizi", key="cam")
        if gambar is not None:
            _proses_foto(gambar.getvalue())
            return
        st.info("📷 Silakan scan label informasi gizi produk.")
        st.markdown(
            '<div class="kartu-info" style="margin-top:12px;">📤 <b>Kamera susah fokus?</b> '
            "Foto dulu pakai kamera HP biasa, lalu pilih fotonya di bawah — hasilnya sama.</div>",
            unsafe_allow_html=True,
        )
        unggah = st.file_uploader("Pilih foto label dari kamera HP / galeri",
                                  type=["jpg", "jpeg", "png"], key="upl")
        if unggah is not None:
            _proses_foto(unggah.getvalue())
        return

    # ---------------- tahap konfirmasi + konsumsi ----------------
    scan = st.session_state.scan or {}
    ui.judul_seksi("🔎 Hasil Pembacaan Label", "Periksa kembali hasil AI dengan label asli — semua angka bisa diedit.")

    sumber = str(scan.get("_sumber", ""))
    if sumber.startswith("gemini"):
        st.caption(f"🤖 Dibaca dengan AI Vision Gemini ({sumber.split(':', 1)[-1]}).")
    elif sumber == "ocr":
        st.caption("🤖 Dibaca dengan OCR.")
        if scan.get("_gemini_error"):
            with st.expander("🤖 Catatan AI Vision (gagal, dipakai OCR cadangan)"):
                st.caption(str(scan.get("_gemini_error")))
    else:
        st.warning("🤖 Pembaca label bermasalah — isi manual sesuai label kemasan.")

    baris_ocr = scan.get("_baris") or []
    if baris_ocr:
        with st.expander("📄 Teks mentah yang terbaca mesin"):
            st.code("\n".join(baris_ocr))

    def ambil(k, d):
        v = scan.get(k)
        return v if v is not None else d

    c1, c2 = st.columns(2)
    nama = c1.text_input("Nama produk (opsional)", key="inp_nama",
                         value=st.session_state.get("nama_produk", "") or "")
    takaran = c2.text_input("Takaran saji", key="inp_takaran",
                            value=str(ambil("takaran_saji", "") or ""),
                            placeholder="contoh: 250 ml / 1 bungkus (35 g)")
    st.session_state.nama_produk = nama

    g1, g2, g3 = st.columns(3)
    gula = g1.number_input("Gula (gram) per sajian", 0.0, 2000.0,
                           float(ambil("gula", 0.0)), 0.1, format="%g", key="inp_gula")
    natrium = g2.number_input("Natrium (mg) per sajian", 0.0, 20000.0,
                              float(ambil("natrium", 0.0)), 1.0, format="%g", key="inp_natrium")
    lemak = g3.number_input("Lemak Total (gram) per sajian", 0.0, 2000.0,
                            float(ambil("lemak", 0.0)), 0.1, format="%g", key="inp_lemak")
    j1, j2 = st.columns(2)
    lemak_jenuh = j1.number_input("Lemak jenuh (gram) per sajian", 0.0, 2000.0,
                                  float(ambil("lemak_jenuh", 0.0)), 0.1, format="%g",
                                  key="inp_lemak_jenuh",
                                  help="Dipakai untuk Nutri-Level (Kemenkes). Di label biasanya tertulis "
                                       "'Lemak Jenuh' / 'Saturated Fat'.")
    isi_default = float(scan.get("isi_sajian") or nl.baca_isi_sajian(takaran) or 0.0)
    isi_sajian = j2.number_input("Isi 1 sajian (mL untuk minuman / gram untuk makanan)",
                                 0.0, 5000.0, isi_default, 1.0, format="%g",
                                 key="inp_isi_sajian",
                                 help="Diambil dari takaran saji, mis. 250 mL atau 12 g. Dipakai untuk "
                                      "mengubah nilai per sajian menjadi nilai per 100 (Nutri-Level).")
    sajian_kemasan = st.number_input("Jumlah sajian per kemasan", 1, 60,
                                     int(ambil("sajian_per_kemasan", 1)), 1,
                                     key="inp_sajian_kemasan")

    per_sajian = {"gula": gula, "natrium": natrium, "lemak": lemak,
                  "lemak_jenuh": lemak_jenuh}

    st.markdown("---")
    st.markdown("#### 🍽️ Berapa sajian yang Anda konsumsi?")
    jumlah = st.number_input("Jumlah sajian dikonsumsi", 0.25, 60.0, 1.0, 0.5,
                             format="%g", key="inp_jumlah")
    st.caption("Contoh: 0.5 sajian = setengah, 1.5 = satu setengah, 2 = habis 2 sajian.")

    # =======================================================================
    # DUA CARA CEK: (1) peraturan Kemenkes (Nutri-Level)  (2) kebutuhan harian
    # =======================================================================
    jenis_awal = nl.tebak_jenis(takaran or scan.get("takaran_saji"))
    tab_nl, tab_har = st.tabs(["🏷️ Cek Nutri-Level (Kemenkes)", "🍽️ Cek Kebutuhan Harianku (GGL)"])

    with tab_nl:
        st.caption("Penilaian mengikuti aturan label depan kemasan: **per 100 mL** untuk minuman, "
                   "**per 100 g** untuk makanan. Huruf akhir = level terburuk dari gula, garam, "
                   "dan lemak jenuh.")
        pilih_jenis = st.radio("Jenis produk", ["Minuman (per 100 mL)", "Makanan (per 100 g)"],
                              index=0 if jenis_awal == "minuman" else 1,
                              horizontal=True, key="inp_jenis_nl")
        jenis_kode = "minuman" if pilih_jenis.startswith("Minuman") else "makanan"
        ambang = setel.ambang_aktif(jenis_kode) or None
        hasil_nl = nl.analisis_nutri_level(
            gula, natrium, lemak_jenuh, isi_sajian=isi_sajian, jenis=jenis_kode,
            ambang=ambang, per100_langsung=(scan.get("_per100") or None))
        st.markdown(ui.kartu_nutri_level(hasil_nl, jenis_kode), unsafe_allow_html=True)
        if not isi_sajian:
            st.warning("⚠️ Isi 1 sajian belum terisi — nilai per 100 mL/g tidak bisa dihitung tepat. "
                       "Isi kolom **Isi 1 sajian** di atas (mis. 250 untuk 250 mL, 12 untuk 12 g).")
        with st.expander("📐 Cara menghitung & ambang batas yang dipakai"):
            st.markdown(
                f"- Nilai label (per sajian) diubah: **nilai ÷ isi 1 sajian × 100**.\n"
                f"- Contoh: gula **{fmt_jumlah(gula)} g** per sajian, isi sajian "
                f"**{fmt_jumlah(isi_sajian)}** → **{fmt_jumlah(hasil_nl['per100']['gula'])} g per 100 "
                f"{'mL' if jenis_kode == 'minuman' else 'g'}**.\n"
                "- Kalau label ikut mencetak kolom *per 100 g/mL*, angka kolom itulah yang dipakai."
            )
            if ambang:
                nama_zat = {"gula": "🍬 Gula (g)", "natrium": "🧂 Garam/natrium (mg)",
                            "lemak_jenuh": "🥑 Lemak jenuh (g)"}
                st.table([{"Zat gizi": nama_zat.get(z, z),
                           "A (rendah)": f"≤ {fmt_jumlah(v[0])}",
                           "B": f"≤ {fmt_jumlah(v[1])}",
                           "C": f"≤ {fmt_jumlah(v[2])}",
                           "D (tinggi)": f"> {fmt_jumlah(v[2])}"}
                          for z, v in ambang.items()])
            if jenis_kode == "makanan" and not ambang:
                st.info("Ambang **makanan (per 100 g)** belum diisi. Buka menu **⚙️ Pengaturan** "
                        "untuk mengisinya sesuai poster/aturan resmi — setelah itu huruf Nutri-Level "
                        "produk makanan dihitung otomatis.")
        st.caption(f"Sumber: {config.NUTRI_LEVEL_SUMBER}. Ini alat bantu edukasi — acuan akhir tetap "
                   "label resmi pada kemasan.")

    with tab_har:
        # lingkaran status produk ini (per 1 sajian) — gaya aplikasi HP
        _rg = ringkas_zat(per_sajian["gula"], config.DAILY_LIMITS["sugar_g"])
        _rn = ringkas_zat(per_sajian["natrium"], config.DAILY_LIMITS["sodium_mg"])
        _rl = ringkas_zat(per_sajian["lemak"], config.DAILY_LIMITS["fat_g"])
        _pp = max([("🍬 GULA", _rg), ("🧂 NATRIUM", _rn), ("🥑 LEMAK", _rl)],
                  key=lambda t: t[1]["persen"])
        st.markdown(ui.donat(
            _pp[1]["persen"], config.COLORS.get(_pp[1]["warna"], "#1565C0"),
            f"PRODUK INI (per 1 sajian) · {_pp[0]}",
            fmt_persen(_pp[1]["persen"]), "% batas harian",
            f"{_pp[1]['badge']} · {_pp[1]['pesan']}",
            f"Zat paling mendekati batas harian pada produk ini "
            f"({fmt_jumlah(_pp[1]['konsumsi'])} dari {fmt_jumlah(_pp[1]['batas'])}).",
        ), unsafe_allow_html=True)

        if not st.session_state.added_ok:
            _blok_kandungan_produk(per_sajian, jumlah)
        else:
            st.success("✅ **Berhasil ditambahkan ke catatan GGL hari ini.** "
                       "Data sudah tersimpan & dashboard diperbarui.")

        st.markdown("---")
        b1, b2 = st.columns([1, 1])
        if not st.session_state.added_ok:
            if b1.button("➕ Tambahkan ke GGL Hari Ini", type="primary",
                         use_container_width=True):
                nama_final = (nama or "").strip() or "Produk (tanpa nama)"
                simpan = dict(per_sajian)
                simpan["_level"] = hasil_nl.get("level")
                tracker.tambah_catatan(
                    nama_produk=nama_final,
                    takaran_saji=(takaran or "").strip(),
                    jumlah_sajian=jumlah,
                    per_sajian=simpan,
                )
                st.session_state.added_ok = True
                st.rerun()
        else:
            st.caption("Data tersimpan. Tekan tombol di bawah untuk scan produk lain.")
        if b2.button("📷 Scan Produk Lain", use_container_width=True):
            reset_scan()
            st.rerun()
        if b1 and not st.session_state.added_ok:
            with b1:
                st.caption("Produk baru masuk catatan hanya setelah tombol ini ditekan.")


# ===========================================================================
# Tabel produk + edit/hapus (dipakai GGL Hari Ini & Riwayat)
# ===========================================================================
def _tabel_produk_editor(baris, judul_tabel: str = "🍽️ Produk yang Dikonsumsi"):
    if not baris:
        st.info("Belum ada produk tercatat pada tanggal ini.")
        return
    ui.judul_seksi(judul_tabel)
    data = []
    for b in baris:
        data.append({
            "Waktu": b["time"], "Produk": b["product_name"] or "-",
            "Jumlah": f"{fmt_jumlah(b['consumed_servings'])} sajian",
            "Gula (g)": fmt_jumlah(b["sugar_g"]),
            "Natrium (mg)": fmt_jumlah(b["sodium_mg"]),
            "Lemak (g)": fmt_jumlah(b["fat_g"]),
            "id": b["id"],
        })
    df = pd.DataFrame(data).set_index("id")
    st.dataframe(df, use_container_width=True, hide_index=True)

    for b in baris:
        rid = b["id"]
        srv_lama = max(float(b["consumed_servings"] or 0), 0.01)
        with st.expander(f"✏️ {b['product_name'] or 'Produk'} — {b['time']} "
                         f"({fmt_jumlah(b['consumed_servings'])} sajian)"):
            e1, e2 = st.columns([2, 1])
            e_nama = e1.text_input("Nama produk", value=b["product_name"] or "",
                                   key=f"en{rid}")
            e_srv = e2.number_input("Jumlah sajian dikonsumsi", 0.25, 60.0,
                                    srv_lama, 0.5, format="%g", key=f"es{rid}")
            st.caption("Nilai gula/natrium/lemak ikut dihitung ulang otomatis "
                       "(proporsional dari kandungan per sajian).")
            simpan, hapus = st.columns(2)
            if simpan.button("💾 Simpan", key=f"sv{rid}"):
                rasio = e_srv / srv_lama
                db.update_consumption(
                    rid, consumed_servings=e_srv,
                    sugar_g=float(b["sugar_g"] or 0) * rasio,
                    sodium_mg=float(b["sodium_mg"] or 0) * rasio,
                    fat_g=float(b["fat_g"] or 0) * rasio,
                    product_name=(e_nama or "").strip() or None)
                st.success("Tersimpan ✅")
                st.rerun()
            if hapus.button("🗑️ Hapus", key=f"del{rid}"):
                db.delete_consumption(rid)
                st.success("Dihapus 🗑️")
                st.rerun()


# ===========================================================================
# 📊 GGL HARI INI
# ===========================================================================
def halaman_ggl_hari_ini():
    ui.judul_seksi("📊 GGL Hari Ini", tanggal_id(_dt.date.today()))
    r = tracker.ringkasan_tanggal()
    g, n, l = (r["ringkasan"]["gula"], r["ringkasan"]["natrium"], r["ringkasan"]["lemak"])

    _kartu_3([
        ui.kartu_total("🍬", "GULA", g["konsumsi"], g["batas"], "g", g),
        ui.kartu_total("🧂", "GARAM / NATRIUM", n["konsumsi"], n["batas"], "mg", n,
                       baris_tambahan=[
                           f"≈ {fmt_jumlah(n['garam_g'])} / {fmt_jumlah(n['garam_batas_g'])} g garam"]),
        ui.kartu_total("🥑", "LEMAK TOTAL", l["konsumsi"], l["batas"], "g", l),
    ])
    badge_teks, pesan = badge(r["status_keseluruhan"])
    st.markdown(f"#### Status konsumsi hari ini: {badge_teks} · {pesan}")

    # ---- Sisa batas ----
    with st.expander("SISA BATAS HARI INI", expanded=True):
        for meta in config.NUTRIENTS:
            rr = r["ringkasan"][meta["key"]]
            if rr["lebih"] > 0:
                st.markdown(f"- {meta['emoji']} **{meta['jenis']}**: 🔴 sudah **melebihi batas "
                            f"{fmt_jumlah(rr['lebih'])} {meta['unit']}** (konsumsi "
                            f"{fmt_jumlah(rr['konsumsi'])} / {fmt_jumlah(rr['batas'])} {meta['unit']})")
            else:
                st.markdown(f"- {meta['emoji']} **{meta['jenis']}**: "
                            f"**{fmt_jumlah(rr['sisa'])} {meta['unit']}** tersisa "
                            f"(batas {fmt_jumlah(rr['batas'])} {meta['unit']})")

    # ---- Kontributor terbesar ----
    kontributor = tracker.kontributor_hari_ini()
    ada = any(kontributor.values())
    if ada:
        ui.judul_seksi("🔎 Kontributor GGL Hari Ini")
        k1, k2, k3 = st.columns(3)
        for kol, meta in zip((k1, k2, k3), config.NUTRIENTS):
            kt = kontributor[meta["key"]]
            if kt and kt["nilai"] > 0:
                kol.markdown(
                    f"**{meta['emoji']} {meta['jenis']} tertinggi**  \n"
                    f"{kt['nama']}  \n**{fmt_jumlah(kt['nilai'])} {meta['unit']}**  \n"
                    f"<small style='color:#5F7A93'>pukul {kt['waktu']}</small>",
                    unsafe_allow_html=True)
            else:
                kol.markdown(f"**{meta['emoji']} {meta['jenis']}**  \n—")

    st.markdown("---")
    _tabel_produk_editor(r["baris"])
    if r["baris"]:
        st.markdown(
            f"**TOTAL HARI INI** — Gula: **{fmt_jumlah(g['konsumsi'])} g** · "
            f"Natrium: **{fmt_jumlah(n['konsumsi'])} mg** · "
            f"Lemak: **{fmt_jumlah(l['konsumsi'])} g**"
        )


# ===========================================================================
# 📅 RIWAYAT
# ===========================================================================
def halaman_riwayat():
    ui.judul_seksi("📅 Riwayat GGL", "Lihat catatan konsumsi di tanggal lain.")
    n1, n2, n3 = st.columns([1, 3, 1])
    if n1.button("◀ Sebelumnya", use_container_width=True):
        st.session_state.hist_date = st.session_state.hist_date - _dt.timedelta(days=1)
        st.rerun()
    tgl = n2.date_input("Pilih tanggal", key="hist_date", max_value=_dt.date.today(),
                        label_visibility="collapsed")
    if n3.button("Berikutnya ▶", use_container_width=True,
                 disabled=tgl >= _dt.date.today()):
        st.session_state.hist_date = st.session_state.hist_date + _dt.timedelta(days=1)
        st.rerun()

    iso = tgl.isoformat()
    r = tracker.ringkasan_tanggal(iso)
    st.markdown(f"#### {tanggal_id(tgl)}")
    g, n, l = (r["ringkasan"]["gula"], r["ringkasan"]["natrium"], r["ringkasan"]["lemak"])
    m1, m2, m3 = st.columns(3)
    m1.metric("🍬 Gula", f"{fmt_jumlah(g['konsumsi'])} / {fmt_jumlah(g['batas'])} g",
              f"{fmt_persen(g['persen'])}% · sisa {fmt_jumlah(g['sisa'])} g")
    m2.metric("🧂 Natrium", f"{fmt_jumlah(n['konsumsi'])} / {fmt_jumlah(n['batas'])} mg",
              f"{fmt_persen(n['persen'])}% · sisa {fmt_jumlah(n['sisa'])} mg")
    m3.metric("🥑 Lemak", f"{fmt_jumlah(l['konsumsi'])} / {fmt_jumlah(l['batas'])} g",
              f"{fmt_persen(l['persen'])}% · sisa {fmt_jumlah(l['sisa'])} g")
    st.markdown("---")
    _tabel_produk_editor(r["baris"], "🍽️ Produk pada Tanggal Ini")

    # cadangkan semua data (CSV)
    with st.expander("💾 Cadangkan / unduh seluruh riwayat (CSV)"):
        semua = db.get_all_consumption()
        if semua:
            df = pd.DataFrame([dict(x) for x in semua])
            st.download_button("⬇️ Unduh CSV", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"gizilens_riwayat_{today_iso()}.csv", mime="text/csv")
        else:
            st.caption("Belum ada data.")


# ===========================================================================
# 📈 RINGKASAN 7 HARI
# ===========================================================================
def halaman_ringkasan():
    ui.judul_seksi("📈 Ringkasan GGL", "Lihat hari ini saja, atau tren beberapa hari terakhir.")
    pilihan = st.radio("Rentang waktu", ["Hari ini", "7 hari terakhir", "30 hari terakhir"],
                       index=0, horizontal=True, key="inp_rentang")
    hari = 1 if pilihan.startswith("Hari ini") else (7 if pilihan.startswith("7") else 30)

    if hari == 1:
        r = tracker.ringkasan_tanggal()
        g, n, l = r["ringkasan"]["gula"], r["ringkasan"]["natrium"], r["ringkasan"]["lemak"]
        _kartu_3([
            ui.kartu_total("🍬", "GULA", g["konsumsi"], g["batas"], "g", g),
            ui.kartu_total("🧂", "GARAM / NATRIUM", n["konsumsi"], n["batas"], "mg", n,
                           baris_tambahan=[f"≈ {fmt_jumlah(n['garam_g'])} g garam"]),
            ui.kartu_total("🥑", "LEMAK TOTAL", l["konsumsi"], l["batas"], "g", l),
        ])
        badge_teks, pesan = badge(r["status_keseluruhan"])
        st.markdown(f"#### Status hari ini: {badge_teks} · {pesan}")
        if r["baris"]:
            st.markdown("#### 🕒 Urutan konsumsi hari ini")
            for b in r["baris"]:
                lvl = f" · 🏷️ Nutri-Level {b.get('nutri_level')}" if dict(b).get("nutri_level") else ""
                st.markdown(
                    f"- **{b['time']}** · {b['product_name']} — {fmt_jumlah(b['consumed_servings'])} sajian · "
                    f"gula {fmt_jumlah(b['sugar_g'])} g · natrium {fmt_jumlah(b['sodium_mg'])} mg · "
                    f"lemak {fmt_jumlah(b['fat_g'])} g{lvl}")
            st.caption("Tombol edit/hapus tiap produk ada di halaman 📊 GGL Hari Ini.")
        else:
            st.info("Belum ada produk tercatat hari ini. Scan produk dulu di menu 📷 Scan Produk.")
        return

    minggu = tracker.ringkasan_rentang(hari)
    df = pd.DataFrame([
        {"Hari": h["label"], "Gula %": round(h["sugar_persen"], 1),
         "Natrium %": round(h["sodium_persen"], 1), "Lemak %": round(h["fat_persen"], 1)}
        for h in minggu["hari"]
    ])
    st.bar_chart(df.set_index("Hari"), height=320, color=["#22c55e", "#f59e0b", "#ef4444"])
    st.caption("Grafik menunjukkan persentase batas harian; nilai di atas 100% = melebihi batas.")

    k1, k2, k3 = st.columns(3)
    peta = [("sugar_g", "sugar_persen", "🍬 Gula"),
            ("sodium_mg", "sodium_persen", "🧂 Natrium"),
            ("fat_g", "fat_persen", "🥑 Lemak")]
    for kol, (kolom, kunci_persen, nama) in zip((k1, k2, k3), peta):
        lewat = minggu["lewat"][kolom]
        baris_terakhir = minggu["hari"][-1]
        kol.markdown(f"**{nama}**  \nHari melebihi batas: **{lewat} dari {len(minggu['hari'])} hari**  \n"
                     f"Hari ini: **{fmt_persen(baris_terakhir[kunci_persen])}%**")

    with st.expander("📋 Rincian per hari"):
        for h in minggu["hari"]:
            tanda = lambda p: "🔴" if p >= 100 else ("🟡" if p >= 50 else "🟢")
            st.markdown(
                f"- **{h['hari_nama']} ({h['label']})** — Gula {tanda(h['sugar_persen'])} "
                f"{fmt_persen(h['sugar_persen'])}% · Natrium {tanda(h['sodium_persen'])} "
                f"{fmt_persen(h['sodium_persen'])}% · Lemak {tanda(h['fat_persen'])} "
                f"{fmt_persen(h['fat_persen'])}%")


# ===========================================================================
# 📖 EDUKASI
# ===========================================================================
def halaman_edukasi():
    ui.judul_seksi("📖 Edukasi GGL", "Gula, Garam (Natrium) & Lemak")
    st.markdown("""
**Apa itu GGL?**  GGL = **Gula, Garam, Lemak** — tiga zat gizi yang paling sering
berlebih pada makanan & minuman kemasan dan berkaitan dengan risiko obesitas,
diabetes, hipertensi, dan penyakit jantung.

#### Batas konsumsi harian (dewasa)
| Zat | Batas/hari | Setara |
|---|---|---|
| 🍬 Gula | 50 g | ± 4 sendok makan |
| 🧂 Garam/Natrium | 2.000 mg natrium | ± 1 sendok teh garam (5 g) |
| 🥑 Lemak | 67 g | ± 5 sendok makan |

*Sumber: Permenkes RI No. 30 Tahun 2013 (informasi GGL pada pangan olahan) &
rekomendasi WHO. Kebutuhan tiap orang bisa berbeda.*

#### Arti warna
- 🟢 **Hijau** — konsumsi masih di bawah 50% batas harian: aman.
- 🟡 **Kuning** — sudah 50–99%: mulai perhatikan konsumsi berikutnya.
- 🔴 **Merah** — sudah ≥100%: melebihi batas harian; batasi asupan lain.

#### Tips
1. Baca label **Informasi Nilai Gizi** sebelum membeli/mengonsumsi.
2. Perhatikan **takaran saji** — satu kemasan bisa berisi beberapa sajian!
3. Batasi minuman manis, camilan asin, dan gorengan dalam sehari.
4. Utamakan air putih, buah, sayur, dan makanan segar.
""")
    with st.expander("📄 Cara memakai GiziLens"):
        st.markdown("""
1. **📷 Scan Produk** → foto label Informasi Nilai Gizi (atau pilih foto dari galeri).
2. **🔎 Periksa hasil** → pastikan angka gula/natrium/lemak sesuai label; edit kalau perlu.
3. **🍽️ Pilih jumlah sajian** yang benar-benar kamu konsumsi (bisa 0.5, 1, 1.5, dst).
4. Lihat **dampaknya** ke total harian sebelum memutuskan.
5. Tekan **➕ Tambahkan ke GGL Hari Ini** — data tersimpan di database lokal.
6. Pantau **📊 GGL Hari Ini**, **📅 Riwayat**, dan **📈 Ringkasan 7 Hari**.
""")


# ===========================================================================
# ℹ️ TENTANG
# ===========================================================================
def halaman_tentang():
    ui.judul_seksi("ℹ️ Tentang GiziLens")
    st.markdown(f"""
**GiziLens** adalah alat edukasi & pencatatan konsumsi GGL (Gula, Garam/Natrium,
Lemak) dari label Informasi Nilai Gizi makanan/minuman kemasan.

- **Pembacaan label**: kamera + AI/OCR. Jika kunci `GEMINI_API_KEY` terpasang di
  pengaturan aplikasi, foto dikirim ke **AI Vision Google (Gemini)** untuk dibaca —
  kalau tidak, dipakai OCR lokal di server (foto tidak disimpan setelah diproses).
- **Penyimpanan**: SQLite lokal (`data/gizilens.db`) — riwayat tetap tersimpan saat
  aplikasi ditutup/refresh; tidak dikirim ke layanan eksternal.
""")
    if db.lokasi_db_cadangan():
        st.warning("ℹ️ Saat ini database tersimpan di folder sementara server "
                   "(folder aplikasi tidak bisa ditulis). Data bisa hilang jika server mati — "
                   "gunakan tombol unduh CSV di halaman Riwayat untuk cadangan.")
    st.markdown("""
#### Sumber batas GGL
- **Permenkes RI No. 30 Tahun 2013** — Informasi Kandungan Gula, Garam, dan Lemak
  untuk Pangan Olahan & Pangan Siap Saji (gula ≤ 50 g, natrium ≤ 2.000 mg,
  lemak ≤ 67 g per hari).
- **WHO** — rekomendasi gula < 10% energi & natrium < 2.000 mg/hari.
- AAL energi 2.150 kkal dipakai label pangan Indonesia (BPOM) untuk %AKG.

#### ⚠️ Disclaimer
GiziLens merupakan **alat edukasi dan pencatatan konsumsi**.

Hasil dihitung berdasarkan informasi nilai gizi pada label produk dan jumlah
konsumsi yang dicatat pengguna. Hasil pembacaan AI/OCR dapat mengalami kesalahan —
selalu periksa kembali hasil scan dengan label asli produk. Batas konsumsi yang
digunakan merupakan acuan umum dan kebutuhan setiap individu dapat berbeda.
GiziLens **tidak digunakan untuk diagnosis** atau menggantikan konsultasi dengan
dokter maupun ahli gizi.

*Dikembangkan oleh {config.ORG}. © 2026*
""")


# ===========================================================================
# ROUTER UTAMA
# ===========================================================================
sidebar()
halaman = st.session_state.nav
if halaman.startswith("🏠"):
    halaman_beranda()
elif halaman.startswith("📷"):
    halaman_scan()
elif halaman.startswith("📊"):
    halaman_ggl_hari_ini()
elif halaman.startswith("📅"):
    halaman_riwayat()
elif halaman.startswith("📈"):
    halaman_ringkasan()
elif halaman.startswith("📖"):
    halaman_edukasi()
elif halaman.startswith("⚙️"):
    halaman_pengaturan()
else:
    halaman_tentang()

ui.footer()
