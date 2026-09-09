"""
Nutri Level — Scan label Informasi Nilai Gizi, cek level gula/natrium/lemak.

Alur: kamera -> AI/OCR baca -> konfirmasi hasil (bisa diedit) -> analisis 🟢🟡🔴
Jalankan:  streamlit run app.py
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from nutri_core import (
    NUTRIENTS,
    DAILY_LIMITS,
    STATUS_THRESHOLDS,
    analisis_produk,
    read_nutrition_label,
)

# ---------------------------------------------------------------------------
# Tampilan (palet biru RSPAL)
# ---------------------------------------------------------------------------
BIRU_TUA = "#0A2E6E"
BIRU = "#1565C0"
BIRU_MUDA = "#42A5F5"
BIRU_PALE = "#EAF1FB"
TEKS = "#10233F"
ABU = "#5F7A93"
HIJAU = "#059669"
KUNING = "#D97706"
MERAH = "#DC2626"

_WARNA = {"hijau": HIJAU, "kuning": KUNING, "merah": MERAH}
_BG_SOFT = {"hijau": "#E9F7F1", "kuning": "#FEF4E5", "merah": "#FDECEC"}

st.set_page_config(
    page_title="Nutri Level — Scan Label Gizi",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif; }}
  .stApp {{
    background:
      radial-gradient(1100px 460px at 88% -8%, #EAF1FB 0%, rgba(234,241,251,0) 60%),
      linear-gradient(180deg, #F7FAFD 0%, #F1F6FC 100%);
  }}
  [data-testid="stAppViewContainer"] {{
    background:
      radial-gradient(1100px 460px at 88% -8%, #EAF1FB 0%, rgba(234,241,251,0) 60%),
      linear-gradient(180deg, #F7FAFD 0%, #F1F6FC 100%) !important;
  }}
  [data-testid="stHeader"] {{ background: transparent; }}

  /* ---------- Kamera: bingkai rapi, bukan kotak "cekung" ---------- */
  [data-testid="stCameraInput"] {{
    border: 1px solid #D8E6F5 !important;
    border-radius: 18px !important;
    overflow: hidden;
    box-shadow: 0 4px 14px rgba(10,46,110,.08);
  }}
  [data-testid="stCameraInput"] video {{
    object-fit: cover;
  }}
  h1, h2, h3 {{ color: {BIRU_TUA}; }}

  /* ---------- Hero ---------- */
  .hero {{
    position: relative; overflow: hidden;
    background: linear-gradient(120deg, {BIRU_TUA} 0%, {BIRU} 58%, #2E86DE 100%);
    border-radius: 24px; padding: 26px 30px 22px; margin: 6px 0 6px;
    box-shadow: 0 10px 30px rgba(10,46,110,.22); color: #fff; text-align: center;
  }}
  .hero .orn {{ position: absolute; opacity: .13; user-select: none; pointer-events: none; }}
  .hero-logo {{ height: 62px; margin-bottom: 4px; filter: drop-shadow(0 2px 4px rgba(0,0,0,.15)); }}
  .hero h1 {{ color: #fff; font-size: 34px; font-weight: 800; margin: 2px 0 2px; letter-spacing: .3px; }}
  .hero-org {{ color: #D8E6FB; font-size: 13px; font-weight: 600; margin-bottom: 6px; }}
  .hero p {{ color: #EAF2FF; font-size: 15px; margin: 4px 0 10px; }}
  .lencana {{
    display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.35);
    color: #fff; font-size: 12.5px; font-weight: 600; border-radius: 999px; padding: 4px 13px; margin: 2px 3px;
  }}
  .hero .fitur-row {{ margin-top: 10px; }}
  .hero .fitur {{
    display: inline-flex; align-items: center; gap: 7px; margin: 3px 5px;
    background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.3);
    border-radius: 14px; padding: 7px 13px; font-size: 13px; font-weight: 600;
  }}

  /* ---------- Panel umum ---------- */
  .panel {{ background:#fff; border:1px solid #E2EDF8; border-radius:18px;
            padding:16px 18px; margin:10px 0; box-shadow:0 3px 12px rgba(10,46,110,.05); }}
  .judul-seksi {{ font-size:20px; font-weight:800; color:{BIRU_TUA}; margin:18px 0 2px; }}
  .sub-seksi {{ color:{ABU}; font-size:13.5px; margin-bottom:10px; }}
  .kartu-info {{ background:{BIRU_PALE}; border-left:4px solid {BIRU}; border-radius:10px;
                 padding:10px 14px; font-size:14px; color:{TEKS}; margin:8px 0; }}
  .kartu-peringatan {{ background:linear-gradient(120deg,#7F1D1D,#DC2626); color:#fff; border-radius:16px;
                      padding:16px 20px; margin:14px 0 8px; box-shadow:0 8px 22px rgba(220,38,38,.25); }}
  .kartu-peringatan b {{ font-size:17px; }}
  .kartu-peringatan p {{ margin:6px 0 0; font-size:14.5px; line-height:1.55; }}
  .kartu-warning {{ background:#FFF7E6; border:1px solid #F5D68C; border-left:5px solid {KUNING};
                   border-radius:10px; padding:10px 14px; font-size:14px; color:#7A4E03; margin:8px 0; }}

  /* ---------- Kartu hasil nutrisi ---------- */
  .nc {{ border:1px solid #E2EDF8; border-top:5px solid {BIRU}; border-radius:16px; background:#fff;
        padding:14px 12px 12px; text-align:center; margin-top:6px;
        box-shadow:0 3px 12px rgba(10,46,110,.06); height:100%; }}
  .nc .nc-head {{ font-size:13px; font-weight:800; color:{TEKS}; letter-spacing:.6px; }}
  .nc .nc-val {{ font-size:30px; font-weight:800; color:{TEKS}; line-height:1.15; margin-top:2px; }}
  .nc .nc-unit {{ font-size:15px; font-weight:700; color:{ABU}; }}
  .nc .nc-pct {{ font-size:13.5px; color:{ABU}; font-weight:600; margin:1px 0 8px; }}
  .nc .nc-bar {{ height:7px; border-radius:99px; background:#EEF3F9; overflow:hidden; margin:0 4px 9px; }}
  .nc .nc-bar i {{ display:block; height:100%; border-radius:99px; }}
  .nc .nc-pill {{ display:inline-block; border-radius:999px; padding:4px 12px; font-size:12.5px;
                 font-weight:800; }}
  .nc .nc-scope {{ font-size:10.5px; color:#A9BBD2; margin-bottom:3px; font-weight:700; }}
  .judul-hasil {{ text-align:center; font-size:23px; font-weight:800; color:{BIRU_TUA};
                 margin:4px 0 0; }}
  .footer-app {{ text-align:center; color:{ABU}; font-size:11.5px; margin-top:26px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

_LOGO = Path(__file__).parent / "assets" / "logo_rspal.png"


def hero():
    logo_b64 = ""
    if _LOGO.exists():
        logo_b64 = base64.b64encode(_LOGO.read_bytes()).decode()
    logo = (
        f'<img class="hero-logo" src="data:image/png;base64,{logo_b64}" alt="RSPAL dr. Ramelan"/>'
        if logo_b64 else ""
    )
    ornamen = "".join(
        f'<span class="orn" style="left:{l};top:{t};transform:rotate({r});font-size:{s}">{e}</span>'
        for e, (l, t, r, s) in zip(
            ["🥫", "🍭", "🥤", "🧀", "🍟", "🧃"],
            [("3%", "8%", "-14deg", "74px"), ("88%", "10%", "10deg", "58px"),
             ("6%", "78%", "9deg", "60px"), ("92%", "80%", "-9deg", "66px"),
             ("2%", "45%", "6deg", "44px"), ("95%", "44%", "-7deg", "42px")],
        )
    )
    st.markdown(
        f'<div class="hero">{ornamen}'
        f'{logo}'
        f'<h1>Nutri Level</h1>'
        f'<div class="hero-org">Sub Departemen Gizi RSPAL dr. Ramelan</div>'
        f'<p>Scan label Informasi Nilai Gizi → tahu level <b>gula</b>, '
        f'<b>natrium</b> &amp; <b>lemak</b> produkmu</p>'
        f'<div class="fitur-row">'
        f'<span class="fitur">📷 Scan label</span>'
        f'<span class="fitur">🤖 AI membaca</span>'
        f'<span class="fitur">🟢🟡🔴 Level nutrisi</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# State & helper
# ---------------------------------------------------------------------------
def ss(k, v):
    if k not in st.session_state:
        st.session_state[k] = v


ss("stage", "scan")          # scan | confirm | result
ss("limits", dict(DAILY_LIMITS))
ss("ambang", dict(STATUS_THRESHOLDS))
ss("scan", None)             # hasil pembacaan AI/OCR
ss("data", None)             # nilai yang dikonfirmasi user
ss("gagal_ocr", None)        # pesan kalau mesin OCR error


def reset_ke_kamera():
    for k in ("scan", "data", "gagal_ocr"):
        st.session_state.pop(k, None)
    st.session_state.stage = "scan"
    st.rerun()


def _fmt_jumlah(v: float) -> str:
    """4 -> '4' ; 18.5 -> '18,5' ; 1250 -> '1.250'"""
    if v is None:
        return "—"
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}".replace(",", ".")
    return f"{v:.1f}".replace(".", ",")


def _fmt_persen(p: float) -> str:
    if p is None:
        return "—"
    if abs(p - round(p)) < 1e-9:
        return str(int(round(p)))
    return f"{p:.1f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Pengaturan batas harian & ambang warna (bisa diubah)
# ---------------------------------------------------------------------------
def bagian_pengaturan():
    with st.expander("⚙️ Ubah batas harian / ambang warna (opsional, default sesuai anjuran)"):
        c1, c2, c3 = st.columns(3)
        st.session_state.limits["sugar_g"] = c1.number_input(
            "🍬 Batas gula (g/hari)", 1.0, 500.0, st.session_state.limits["sugar_g"], 1.0, format="%g"
        )
        st.session_state.limits["sodium_mg"] = c2.number_input(
            "🧂 Batas natrium (mg/hari)", 100.0, 10000.0, st.session_state.limits["sodium_mg"], 50.0, format="%g"
        )
        st.session_state.limits["fat_g"] = c3.number_input(
            "🥑 Batas lemak total (g/hari)", 1.0, 500.0, st.session_state.limits["fat_g"], 1.0, format="%g"
        )
        d1, d2, _ = st.columns(3)
        st.session_state.ambang["warning"] = d1.number_input(
            "🟡 Kuning mulai dari (%)", 1.0, 100.0, st.session_state.ambang["warning"], 1.0, format="%g"
        )
        st.session_state.ambang["danger"] = d2.number_input(
            "🔴 Merah mulai dari (%)", 1.0, 300.0, st.session_state.ambang["danger"], 1.0, format="%g"
        )
        st.caption(
            "📚 Sumber batas harian: Permenkes RI No. 30 Tahun 2013 tentang "
            "Informasi Kandungan Gula, Garam, dan Lemak (gula ≤ 50 g/hari ≈ 4 sdm, "
            "natrium ≤ 2.000 mg/hari ≈ 1 sdt garam, lemak ≤ 67 g/hari ≈ 5 sdm) — "
            "sejalan dengan rekomendasi WHO."
        )


# ---------------------------------------------------------------------------
# Tahap 1: SCAN
# ---------------------------------------------------------------------------
def _kunci_gemini():
    try:
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


def _proses_foto(byte_img: bytes):
    """Foto (dari kamera atau unggahan) -> OCR -> pindah ke tahap konfirmasi."""
    st.success("✅ Foto berhasil diambil.")
    with st.spinner("Sedang membaca informasi nilai gizi..."):
        try:
            hasil = read_nutrition_label(byte_img, gemini_key=_kunci_gemini())
            st.session_state.gagal_ocr = None
        except Exception as exc:
            hasil = {
                "gula": None, "natrium": None, "lemak": None,
                "protein": None, "karbohidrat": None, "energi": None,
                "takaran_saji": None, "sajian_per_kemasan": 1, "nama_produk": None,
                "_baris": [], "_sumber": "gagal",
            }
            st.session_state.gagal_ocr = str(exc)

    st.session_state.scan = hasil
    st.session_state.stage = "confirm"
    st.rerun()


def tahap_scan():
    st.markdown('<div class="judul-seksi">📷 Scan Label Informasi Gizi</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel">Arahkan kamera ke bagian <b>"Informasi Nilai Gizi"</b> pada kemasan.<br><br>'
        "Pastikan:<br>• Label terlihat penuh<br>• Tulisan tidak buram<br>"
        "• Cahaya cukup<br>• Kamera tidak terlalu miring<br>"
        '• Kalau kamera sulit fokus: geser pelan mendekat/menjauh (±15–25 cm) '
        "sampai tulisan tajam, lalu ambil foto</div>",
        unsafe_allow_html=True,
    )

    gambar = st.camera_input("Ambil foto label Informasi Nilai Gizi", key="cam")
    if gambar is not None:
        _proses_foto(gambar.getvalue())
        return

    st.info("📷 Silakan scan label informasi gizi produk.")

    # ---- Jalur cadangan: kamera HP asli (fokus/zoom penuh) atau galeri ----
    st.markdown(
        '<div class="kartu-info" style="margin-top:14px;">📤 <b>Kamera HP-mu susah fokus?</b> '
        "Foto dulu pakai aplikasi kamera HP biasa (bisa ketuk layar untuk fokus & zoom), "
        "lalu pilih fotonya di bawah ini — hasilnya sama saja.</div>",
        unsafe_allow_html=True,
    )
    unggah = st.file_uploader(
        "Pilih foto label dari kamera HP / galeri",
        type=["jpg", "jpeg", "png"],
        key="upl",
    )
    if unggah is not None:
        _proses_foto(unggah.getvalue())


# ---------------------------------------------------------------------------
# Tahap 2: KONFIRMASI hasil AI
# ---------------------------------------------------------------------------
def tahap_konfirmasi():
    st.markdown('<div class="judul-seksi">🔎 Hasil Pembacaan Label</div>', unsafe_allow_html=True)
    scan = st.session_state.scan or {}
    # Kalau user pernah konfirmasi (tombol "Koreksi Angka"), nilai awal = nilai
    # yang terakhir ia konfirmasi, bukan hasil OCR lama.
    sumber = {**scan, **(st.session_state.data or {})}

    if st.session_state.gagal_ocr:
        st.error(
            f"🤖 Mesin pembaca label bermasalah: {st.session_state.gagal_ocr}\n\n"
            "Kamu tetap bisa memakai aplikasi: isi nilai langsung dari label di bawah ini."
        )
    else:
        if str(scan.get("_sumber", "")).startswith("gemini"):
            model = str(scan.get("_sumber")).split(":", 1)[-1]
            st.caption(f"🤖 Dibaca dengan AI Vision Gemini ({model}).")
        else:
            st.caption("🤖 Dibaca dengan OCR.")
        if scan.get("_gemini_error"):
            with st.expander("🤖 Catatan AI Vision (gagal, dipakai OCR cadangan)"):
                st.caption(str(scan.get("_gemini_error")))
        baris = scan.get("_baris") or []
        if baris:
            with st.expander("📄 Teks mentah yang terbaca mesin"):
                st.code("\n".join(baris))

        tidak_terbaca = sumber.get("gula") is None and sumber.get("natrium") is None and sumber.get("lemak") is None
        if tidak_terbaca:
            st.warning(
                "🤖 Angka gula/natrium/lemak tidak terbaca dengan yakin. "
                "Isi manual sesuai label pada kemasan ya."
            )

    k = lambda nama, d: sumber.get(nama) if sumber.get(nama) is not None else d

    c1, c2 = st.columns(2)
    takaran = c1.text_input(
        "Takaran saji", value=k("takaran_saji", "") or "",
        placeholder="contoh: 250 ml / 1 bungkus (35 g)",
    )
    sajian = c2.number_input(
        "Jumlah sajian per kemasan", 1, 60, int(k("sajian_per_kemasan", 1)), 1
    )

    g1, g2, g3 = st.columns(3)
    gula = g1.number_input("Gula (gram)", 0.0, 2000.0, float(k("gula", 0.0)), 0.1, format="%g")
    natrium = g2.number_input("Natrium (mg)", 0.0, 20000.0, float(k("natrium", 0.0)), 1.0, format="%g")
    lemak = g3.number_input("Lemak Total (gram)", 0.0, 2000.0, float(k("lemak", 0.0)), 0.1, format="%g")

    st.markdown(
        '<div class="kartu-warning">⚠️ <b>Periksa kembali hasil pembacaan AI dengan label pada '
        "kemasan sebelum melakukan analisis.</b> Semua angka di atas bisa diedit kalau ada yang "
        "tidak sesuai.</div>",
        unsafe_allow_html=True,
    )

    b1, b2 = st.columns([1, 1])
    if b1.button("✅ Konfirmasi & Analisis", type="primary", use_container_width=True):
        st.session_state.data = {
            "takaran_saji": (takaran or "").strip() or None,
            "sajian_per_kemasan": int(sajian),
            "gula": float(gula),
            "natrium": float(natrium),
            "lemak": float(lemak),
            "nama_produk": scan.get("nama_produk"),
        }
        st.session_state.stage = "result"
        st.rerun()
    if b2.button("📷 Ambil Foto Ulang", use_container_width=True):
        st.session_state.pop("scan", None)
        st.session_state.pop("data", None)
        st.session_state.pop("gagal_ocr", None)
        st.session_state.stage = "scan"
        st.rerun()


# ---------------------------------------------------------------------------
# Kartu hasil per zat gizi
# ---------------------------------------------------------------------------
def _kartu_html(meta: dict, stat: dict, scope: str):
    if stat is None:
        return ""
    warna = _WARNA[stat["warna"]]
    bg = _BG_SOFT[stat["warna"]]
    lebar_bar = max(2.0, min(100.0, stat["persen"]))
    return f"""
    <div class="nc" style="border-top-color:{warna};">
      <div class="nc-scope">{scope}</div>
      <div class="nc-head">{meta['emoji']} {meta['label']}</div>
      <div class="nc-val">{_fmt_jumlah(stat['nilai'])}<span class="nc-unit"> {meta['unit']}</span></div>
      <div class="nc-pct">{_fmt_persen(stat['persen'])}% batas harian</div>
      <div class="nc-bar"><i style="width:{lebar_bar}%;background:{warna};"></i></div>
      <div class="nc-pill" style="color:{warna};background:{bg};">{stat['badge']} · {stat['pesan']}</div>
    </div>"""


def _deret_kartu(analisis: dict, skala: str):
    if skala == "kemasan":
        stats = analisis["per_kemasan"]
        scope = "1 KEMASAN"
    else:
        stats = analisis["per_sajian"]
        scope = "1 SAJIAN"
    cols = st.columns(3)
    for col, meta in zip(cols, NUTRIENTS):
        col.markdown(_kartu_html(meta, stats[meta["key"]], scope), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tahap 3: HASIL ANALISIS
# ---------------------------------------------------------------------------
def tahap_hasil():
    data = st.session_state.data
    if not data:
        reset_ke_kamera()
        return

    analisis = analisis_produk(data, st.session_state.limits, st.session_state.ambang)
    n = analisis["sajian_per_kemasan"]

    st.markdown('<div class="judul-hasil">📊 HASIL ANALISIS PRODUK</div>', unsafe_allow_html=True)
    ket = []
    if data.get("takaran_saji"):
        ket.append(f"Takaran saji: {data['takaran_saji']}")
    ket.append(f"{n} sajian per kemasan")
    st.markdown(
        f'<div class="sub-seksi" style="text-align:center;">{" · ".join(ket)}</div>',
        unsafe_allow_html=True,
    )

    # ----- per sajian -----
    st.markdown('<div class="judul-seksi">🥄 Nilai per 1 Sajian</div>', unsafe_allow_html=True)
    _deret_kartu(analisis, "sajian")

    # ----- per kemasan (kalau > 1 sajian) -----
    if n > 1:
        st.markdown(
            f'<div class="judul-seksi" style="margin-top:26px;">📦 Jika 1 Kemasan Dikonsumsi Seluruhnya '
            f'<span style="font-size:12px;color:{ABU};">({n} × nilai per sajian)</span></div>',
            unsafe_allow_html=True,
        )
        _deret_kartu(analisis, "kemasan")

    # ----- peringatan -----
    if analisis["ada_merah"]:
        merah_sajian = any(
            s and s["warna"] == "merah" for s in analisis["per_sajian"].values()
        )
        kalimat = (
            "Kandungan salah satu zat gizi pada produk ini telah mencapai atau melebihi "
            "batas konsumsi harian."
        )
        if not merah_sajian:
            kalimat += (
                " Nilai per sajiannya masih aman, tetapi jika satu kemasan dihabiskan "
                "sekaligus, batas harian bisa terlampaui."
            )
        kalimat += " Perhatikan konsumsi makanan dan minuman lain sepanjang hari."
        st.markdown(
            f'<div class="kartu-peringatan"><b>⚠️ PERINGATAN</b><p>{kalimat}</p></div>',
            unsafe_allow_html=True,
        )

    with st.expander("ℹ️ Batas harian & ambang yang dipakai"):
        st.markdown(
            f"- 🍬 Gula: **{_fmt_jumlah(st.session_state.limits['sugar_g'])} g/hari**\n"
            f"- 🧂 Natrium: **{_fmt_jumlah(st.session_state.limits['sodium_mg'])} mg/hari**\n"
            f"- 🥑 Lemak total: **{_fmt_jumlah(st.session_state.limits['fat_g'])} g/hari**\n\n"
            f"- 🟢 Hijau: 0–{_fmt_persen(st.session_state.ambang['warning'] - 1)}% batas harian\n"
            f"- 🟡 Kuning: {_fmt_persen(st.session_state.ambang['warning'])}–"
            f"{_fmt_persen(st.session_state.ambang['danger'] - 1)}%\n"
            f"- 🔴 Merah: ≥ {_fmt_persen(st.session_state.ambang['danger'])}%\n\n"
            "**📚 Sumber:**\n"
            "- Batas gula, natrium & lemak: **Permenkes RI No. 30 Tahun 2013** "
            "(Informasi Kandungan Gula, Garam, dan Lemak untuk Pangan Olahan & "
            "Pangan Siap Saji) — gula ≤ 50 g (≈4 sdm), natrium ≤ 2.000 mg (≈1 sdt garam), "
            "lemak ≤ 67 g (≈5 sdm) per orang per hari.\n"
            "- Nilai ini sejalan dengan rekomendasi **WHO** (gula < 10% energi, "
            "natrium < 2.000 mg/hari).\n"
            "- Angka Acuan Label (AAL) energi **2.150 kkal** dipakai label pangan "
            "Indonesia (BPOM) untuk menghitung %AKG."
        )

    st.markdown("---")
    b1, b2 = st.columns([1, 1])
    if b1.button("📷 Scan Produk Lain", type="primary", use_container_width=True):
        reset_ke_kamera()
    if b2.button("✏️ Koreksi Angka", use_container_width=True):
        st.session_state.stage = "confirm"
        st.rerun()


# ---------------------------------------------------------------------------
# Utama
# ---------------------------------------------------------------------------
hero()
bagian_pengaturan()

if st.session_state.stage == "scan":
    tahap_scan()
elif st.session_state.stage == "confirm":
    tahap_konfirmasi()
else:
    tahap_hasil()

st.markdown(
    '<div class="footer-app">Aplikasi Nutri Level · foto diproses otomatis untuk membaca label '
    '&amp; tidak disimpan · dibuat oleh Sub Departemen Gizi RSPAL dr. Ramelan · © 2026</div>',
    unsafe_allow_html=True,
)
