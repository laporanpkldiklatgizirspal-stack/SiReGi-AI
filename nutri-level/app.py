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
st.markdown(ui.css(), unsafe_allow_html=True)

NAV = [
    "🏠 Beranda",
    "📷 Scan Produk",
    "📊 GGL Hari Ini",
    "📅 Riwayat",
    "📈 Ringkasan 7 Hari",
    "📖 Edukasi",
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
    sajian_kemasan = st.number_input("Jumlah sajian per kemasan", 1, 60,
                                     int(ambil("sajian_per_kemasan", 1)), 1,
                                     key="inp_sajian_kemasan")

    st.markdown("---")
    st.markdown("#### 🍽️ Berapa sajian yang Anda konsumsi?")
    jumlah = st.number_input("Jumlah sajian dikonsumsi", 0.25, 60.0, 1.0, 0.5,
                             format="%g", key="inp_jumlah")
    st.caption("Contoh: 0.5 sajian = setengah, 1.5 = satu setengah, 2 = habis 2 sajian.")

    per_sajian = {"gula": gula, "natrium": natrium, "lemak": lemak}
    if not st.session_state.added_ok:
        dampak = _blok_kandungan_produk(per_sajian, jumlah)
    else:
        st.success("✅ **Berhasil ditambahkan ke catatan GGL hari ini.** "
                   "Data sudah tersimpan & dashboard diperbarui.")

    st.markdown("---")
    b1, b2 = st.columns([1, 1])
    if not st.session_state.added_ok:
        if b1.button("➕ Tambahkan ke GGL Hari Ini", type="primary",
                     use_container_width=True):
            nama_final = (nama or "").strip() or "Produk (tanpa nama)"
            tracker.tambah_catatan(
                nama_produk=nama_final,
                takaran_saji=(takaran or "").strip(),
                jumlah_sajian=jumlah,
                per_sajian=per_sajian,
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
    ui.judul_seksi("📈 Ringkasan 7 Hari", "Persentase konsumsi terhadap batas harian (7 hari terakhir).")
    minggu = tracker.ringkasan_7_hari()
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
        kol.markdown(f"**{nama}**  \nHari melebihi batas: **{lewat} dari 7 hari**  \n"
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
else:
    halaman_tentang()

ui.footer()
