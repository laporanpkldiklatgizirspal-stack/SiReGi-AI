"""
Aplikasi Recall Gizi + Database TKPI (Web) — gaya NutriSurvey
Tema warna: biru (selaras identitas RSPAL)
Jalankan:  streamlit run app.py
"""

from __future__ import annotations

import base64
import datetime
import io
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import parser_recall as pr
from utils import recall_engine as reng
from utils import menu_store as ms
from utils import ai_recall as air
from utils import buku_foto as bf

FILE_BAWAAN = Path(__file__).parent / "data" / "MASTER_TKPI__Recall.xlsx"
MENU_FILE = Path(__file__).parent / "data" / "MENU_GIZI.xlsx"

# Palet biru RSPAL
BIRU_TUA = "#0A2E6E"
BIRU = "#1565C0"
BIRU_MUDA = "#42A5F5"
BIRU_PALE = "#EAF1FB"
TEKS = "#10233F"
ABU = "#5F7A93"
HIJAU = "#059669"
KUNING = "#D97706"
MERAH = "#DC2626"

st.set_page_config(
    page_title="Recall Gizi + TKPI",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

  html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif;
  }}
  .stApp {{
    background:
      radial-gradient(1200px 500px at 85% -10%, #EAF1FB 0%, rgba(234,241,251,0) 60%),
      linear-gradient(180deg, #F7FAFD 0%, #F2F7FC 100%);
  }}
  [data-testid="stHeader"] {{ background: transparent; }}

  /* ---------- Sidebar disembunyikan (tampilan kiri tidak dipakai) ---------- */
  [data-testid="stSidebar"] {{ display: none !important; }}
  section[data-testid="stSidebarContent"] {{ display: none !important; }}

  /* ---------- Sidebar ---------- */
  [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #FFFFFF 0%, #F4F8FD 100%);
    border-right: 1px solid #E3ECF6;
  }}
  .sisi-logo {{
    background: linear-gradient(135deg, {BIRU_TUA} 0%, {BIRU} 100%);
    border-radius: 16px; padding: 14px 14px 12px; margin-bottom: 10px;
    color: #fff; box-shadow: 0 6px 18px rgba(21,101,192,.25);
  }}
  .sisi-logo .sisi-judul {{ font-size: 18px; font-weight: 800; }}
  .sisi-logo .sisi-sub {{ font-size: 11.5px; opacity: .85; margin-top: 2px; }}
  .sisi-chip {{
    background: #fff; border: 1px solid #E3ECF6; border-radius: 10px;
    padding: 7px 10px; margin-top: 6px; font-size: 12px; color: {TEKS};
    box-shadow: 0 1px 3px rgba(16,35,63,.05);
  }}

  /* ---------- Hero ---------- */
  .hero {{
    background:
      radial-gradient(900px 400px at 88% -25%, rgba(255,255,255,.16) 0%, rgba(255,255,255,0) 60%),
      linear-gradient(120deg, {BIRU_TUA} 0%, {BIRU} 52%, #2E7EDB 100%);
    border-radius: 26px; padding: 36px 38px 32px; color: #fff; position: relative;
    overflow: hidden; box-shadow: 0 14px 38px rgba(10,46,110,.28);
    margin-bottom: 10px; text-align: center;
  }}
  .hero:after {{
    content: ""; position: absolute; right: -80px; top: -80px; width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(255,255,255,.15) 0%, transparent 70%);
  }}
  .hero:before {{
    content: "🍽️"; position: absolute; left: 24px; bottom: -10px; font-size: 120px;
    opacity: .10; transform: rotate(-10deg);
  }}
  .hero .hero-logo {{
    height: 112px; width: auto; margin: 0 auto 16px; display: block;
    filter: drop-shadow(0 8px 16px rgba(10,46,110,.35));
  }}
  .hero h1 {{
    font-size: 32px; font-weight: 800; margin: 0 auto 12px; letter-spacing: .1px;
    line-height: 1.25; max-width: 880px; text-wrap: balance;
  }}
  .hero .hero-org {{
    display: inline-block; font-size: 15px; font-weight: 700; letter-spacing: 1.4px;
    text-transform: uppercase; color: rgba(255,255,255,.95);
    background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.32);
    padding: 6px 18px; border-radius: 999px; margin-bottom: 16px;
    backdrop-filter: blur(3px);
  }}
  .hero p {{ margin: 0 auto; font-size: 15px; opacity: .93; max-width: 680px; line-height: 1.62; }}
  .hero .lencana {{ display: inline-block; background: rgba(255,255,255,.16);
    border: 1px solid rgba(255,255,255,.32); border-radius: 20px; padding: 5px 14px;
    font-size: 12.5px; font-weight: 600; margin: 14px 5px 0 0; backdrop-filter: blur(2px); }}
  .hero .orn {{ position: absolute; opacity: .13; pointer-events: none;
    user-select: none; filter: drop-shadow(0 6px 14px rgba(10,46,110,.25)); }}
  .hero .konten {{ position: relative; z-index: 1; }}
  .hero .fitur-row {{ display: flex; justify-content: center; gap: 12px;
    flex-wrap: wrap; margin-top: 20px; }}
  .hero .fitur {{ display: flex; flex-direction: column; align-items: center;
    gap: 5px; min-width: 148px; background: rgba(255,255,255,.14);
    border: 1px solid rgba(255,255,255,.34); border-radius: 16px;
    padding: 13px 18px 11px; backdrop-filter: blur(4px);
    box-shadow: 0 4px 14px rgba(10,46,110,.16); }}
  .hero .fitur .f-ico {{ font-size: 25px; line-height: 1.15; }}
  .hero .fitur .f-lab {{ font-size: 11px; font-weight: 800; letter-spacing: .4px;
    color: rgba(255,255,255,.97); text-transform: uppercase; white-space: nowrap; }}
  @media (max-width: 640px) {{
    .hero {{ padding: 28px 18px 24px; }}
    .hero h1 {{ font-size: 23px; }}
    .hero .hero-org {{ font-size: 11px; letter-spacing: .8px; padding: 5px 12px; }}
    .hero .hero-logo {{ height: 84px; }}
    .hero .orn {{ display: none; }}
    .hero .fitur {{ min-width: 132px; }}
  }}

  /* ---------- Judul seksi ---------- */
  .seksi {{
    font-size: 15px; font-weight: 800; color: {BIRU_TUA}; margin: 18px 0 10px;
    padding-left: 10px; border-left: 4px solid {BIRU}; line-height: 1.3;
  }}

  /* ---------- Kartu KPI ---------- */
  .kpi {{
    background: #fff; border: 1px solid #E3ECF6; border-radius: 14px;
    padding: 12px 14px; box-shadow: 0 2px 8px rgba(16,35,63,.05);
    border-top: 4px solid var(--c); height: 100%;
  }}
  .kpi .kpi-ico {{ font-size: 17px; }}
  .kpi .kpi-lab {{ font-size: 11px; font-weight: 700; letter-spacing: .4px;
    text-transform: uppercase; color: {ABU}; }}
  .kpi .kpi-val {{ font-size: 22px; font-weight: 800; color: {TEKS};
    line-height: 1.2; margin: 3px 0 1px; }}
  .kpi .kpi-val small {{ font-size: 12px; font-weight: 600; color: {ABU}; }}
  .kpi .kpi-sub {{ font-size: 11.5px; color: {ABU}; }}

  /* ---------- Bilah capaian ---------- */
  .cap {{ background: #fff; border: 1px solid #E3ECF6; border-radius: 12px;
    padding: 10px 14px; margin-bottom: 8px; box-shadow: 0 1px 4px rgba(16,35,63,.04); }}
  .cap-head {{ display: flex; justify-content: space-between; align-items: baseline;
    gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }}
  .cap-name {{ font-weight: 700; font-size: 13px; color: {TEKS}; }}
  .cap-pct {{ font-size: 12.5px; font-weight: 800; }}
  .pbar {{ background: #E7EFF8; height: 9px; border-radius: 20px; overflow: hidden; }}
  .pfill {{ height: 100%; border-radius: 20px; }}

  /* ---------- Kotak info kecil ---------- */
  .info-blok {{
    background: #fff; border: 1px solid #E3ECF6; border-radius: 14px;
    padding: 10px 14px; font-size: 12.5px; color: {ABU}; line-height: 1.5;
  }}

  /* ---------- Widget ---------- */
  .stTextInput input, .stNumberInput input, .stSelectbox [data-baseweb="select"] > div,
  .stTextArea textarea {{
    border-radius: 10px !important; border: 1px solid #D7E3F0 !important;
    background: #fff !important;
  }}
  .stTextInput input:focus, .stNumberInput input:focus {{
    border-color: {BIRU} !important; box-shadow: 0 0 0 3px rgba(21,101,192,.12) !important;
  }}
  .stButton > button {{
    border-radius: 10px !important; font-weight: 700 !important;
    border: none !important; box-shadow: 0 3px 10px rgba(21,101,192,.18);
    transition: transform .06s ease;
  }}
  .stButton > button:hover {{ transform: translateY(-1px); }}
  .stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {BIRU_TUA}, {BIRU}) !important; color: #fff !important;
  }}
  .stDownloadButton > button {{
    background: #fff !important; color: {BIRU} !important;
    border: 1.5px solid {BIRU} !important; border-radius: 10px !important; font-weight: 700 !important;
  }}

  /* ---------- Tabs ---------- */
  [data-baseweb="tab-list"] {{ gap: 6px; background: #fff; padding: 6px;
    border-radius: 14px; border: 1px solid #E3ECF6; margin-bottom: 14px; }}
  [data-baseweb="tab"] {{ font-weight: 700; font-size: 14px; border-radius: 10px;
    padding: 8px 16px; }}
  [data-baseweb="tab"][aria-selected="true"] {{
    background: linear-gradient(135deg, {BIRU_TUA}, {BIRU}) !important;
    color: #fff !important; }}
  [data-baseweb="tab-highlight"] {{ display: none; }}

  /* ---------- Dataframe ---------- */
  [data-testid="stDataFrame"] {{
    border: 1px solid #E3ECF6 !important; border-radius: 12px !important;
    overflow: hidden; box-shadow: 0 1px 5px rgba(16,35,63,.04);
  }}

  .footer-app {{ text-align: center; color: {ABU}; font-size: 11.5px;
    margin-top: 26px; padding-top: 12px; border-top: 1px dashed #D7E3F0; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Komponen tampilan
# ------------------------------------------------------------------
def hero(judul: str, sub: str = "", lencana: list[str] | None = None,
         logo_b64: str = "", org: str = "",
         fitur: list[tuple[str, str]] | None = None,
         ornamen: list[str] | None = None):
    logo = (
        '<img class="hero-logo" src="data:image/png;base64,' + logo_b64
        + '" alt="RSPAL dr. Ramelan"/>'
    ) if logo_b64 else ""
    org_html = f'<div class="hero-org">{org}</div>' if org else ""
    sub_html = f"<p>{sub}</p>" if sub else ""
    chip = "".join(f'<span class="lencana">{b}</span>' for b in (lencana or []))
    # Ornamen emoji makanan samar di latar hero (posisi pojok kiri/kanan)
    pos_orn = [
        ("3.5%", "9%", "-14deg", "72px"), ("8%", "46%", "9deg", "52px"),
        ("2.5%", "84%", "-8deg", "60px"), ("94%", "6%", "11deg", "64px"),
        ("89%", "42%", "-11deg", "46px"), ("93%", "84%", "7deg", "66px"),
    ]
    if ornamen:
        orn_html = "".join(
            f'<span class="orn" style="left:{l};top:{t};'
            f'transform:rotate({r});font-size:{s}">{e}</span>'
            for e, (l, t, r, s) in zip(ornamen, pos_orn)
        )
    else:
        orn_html = ""
    if fitur:
        tile = "".join(
            f'<span class="fitur"><span class="f-ico">{ik}</span>'
            f'<span class="f-lab">{lb}</span></span>'
            for ik, lb in fitur
        )
        isi_bawah = f'<div class="fitur-row">{tile}</div>'
    else:
        isi_bawah = chip
    st.markdown(
        f'<div class="hero">{orn_html}'
        f'<div class="konten">{logo}<h1>{judul}</h1>{org_html}{sub_html}{isi_bawah}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def seksi(judul: str):
    st.markdown(f'<div class="seksi">{judul}</div>', unsafe_allow_html=True)


def kartu_kpi(ikon: str, label: str, nilai: str, sub: str = "", aksen: str = BIRU):
    return (
        f'<div class="kpi" style="--c:{aksen}">'
        f'<div><span class="kpi-ico">{ikon}</span> <span class="kpi-lab">{label}</span></div>'
        f'<div class="kpi-val">{nilai}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


def baris_kpi(daftar, n_kolom: int | None = None):
    n = n_kolom or len(daftar)
    cols = st.columns(n)
    for col, k in zip(cols, daftar):
        with col:
            st.markdown(kartu_kpi(**k), unsafe_allow_html=True)


def warna_capaian(pct: float) -> str:
    if pct >= 100:
        return HIJAU, "Tercapai penuh"
    if pct >= 90:
        return "#65A30D", "Hampir penuh"
    if pct >= 75:
        return KUNING, "Perlu ditingkatkan"
    return MERAH, "Jauh dari target"


def bilah_capaian(ikon, nama, nilai, target, satuan):
    pct = min(999.0, nilai / target * 100) if target and target > 0 else 0.0
    warna, ket = warna_capaian(pct)
    lebar = min(100.0, pct)
    return (
        f'<div class="cap">'
        f'<div class="cap-head"><span class="cap-name">{ikon} {nama}</span>'
        f'<span class="cap-pct" style="color:{warna}">{pct:.0f}%</span></div>'
        f'<div class="cap-head" style="margin-bottom:4px">'
        f'<span style="font-size:12px;color:{ABU}">{nilai} dari {target:,.0f} {satuan}</span>'
        f'<span style="font-size:11px;color:{ABU}">{ket}</span></div>'
        f'<div class="pbar"><div class="pfill" style="width:{lebar}%;background:'
        f'linear-gradient(90deg,{warna},#7FD1AE)"></div></div>'
        f'</div>'
    )


def gaya_fig(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans, Segoe UI", color=TEKS),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


# ------------------------------------------------------------------
# Memuat data
# ------------------------------------------------------------------
@st.cache_data(show_spinner="Membaca file Excel...")
def muat_data(sumber, mtime: float = 0.0) -> dict:
    """mtime dipakai supaya cache otomatis baca ulang bila file master disimpan ulang."""
    try:
        if isinstance(sumber, bytes):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                f.write(sumber)
                tmp = f.name
            try:
                tkpi = pr.baca_tkpi(tmp)
                recall = pr.baca_recall(tmp)
            finally:
                Path(tmp).unlink(missing_ok=True)
        else:
            tkpi = pr.baca_tkpi(sumber)
            recall = pr.baca_recall(sumber)
        return {"ok": True, "tkpi": tkpi, "recall": recall}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "pesan": str(exc)}


def fmt(v, desimal: int = 1) -> str:
    try:
        if pd.isna(v):
            return "-"
        return f"{float(v):,.{desimal}f}"
    except Exception:  # noqa: BLE001
        return "-"


# ------------------------------------------------------------------
# MEMUAT DATA MASTER (TKPI + RECALL) — tanpa panel samping
# ------------------------------------------------------------------
if not FILE_BAWAAN.exists():
    st.error("File master bawaan tidak ditemukan di folder data/.")
    st.stop()
data = muat_data(str(FILE_BAWAAN), os.path.getmtime(FILE_BAWAAN))

if not data.get("ok"):
    st.error(f"❌ Gagal membaca file: {data.get('pesan')}")
    st.stop()

tkpi: pd.DataFrame = data["tkpi"]
recall: dict = data["recall"]
items_file: pd.DataFrame = recall["data"]
identitas_file: dict = recall["identitas"]

# ------------------------------------------------------------------
# Katalog Buku Foto Makanan (Kemenkes SKMI) — porsi URT + foto
# ------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def muat_katalog_buku_foto() -> list[dict]:
    return bf.muat_katalog_urt()

KATALOG_BF: list[dict] = muat_katalog_buku_foto()
BASE_APP = Path(__file__).parent

# ------------------------------------------------------------------
# State input recall
# ------------------------------------------------------------------
if "inp_items" not in st.session_state:
    st.session_state.inp_items = []
if "menu_draft" not in st.session_state:
    st.session_state.menu_draft = []
if "menu_log" not in st.session_state:
    st.session_state.menu_log = []


def total_input() -> pd.Series:
    daftar = st.session_state.inp_items
    if not daftar:
        return pd.Series({g: 0.0 for g in pr.NAMA_GIZI})
    return pd.DataFrame([it["zat"] for it in daftar]).sum(numeric_only=True)


JAM_KATEGORI_WAKTU = {
    "Pagi": "06.00–10.00",
    "Siang": "10.00–14.00",
    "Malam": "18.00–22.00",
    "Selingan": "di antara waktu makan",
}

# Jam bawaan per kategori waktu makan (dipakai sebagai nilai awal input jam)
JAM_BAWAAN_KATEGORI = {
    "Pagi": datetime.time(7, 0),
    "Siang": datetime.time(12, 0),
    "Malam": datetime.time(19, 0),
    "Selingan": datetime.time(15, 0),
}


def reset_jam_ikut_kategori() -> None:
    """Saat kategori waktu makan diganti, jam ikut menyesuaikan ke nilai awal."""
    kat = st.session_state.get("inp_waktu", "Pagi")
    st.session_state["inp_jam"] = JAM_BAWAAN_KATEGORI.get(kat, datetime.time(7, 0))


def rekap_per_waktu_tabel(df: pd.DataFrame) -> pd.DataFrame:
    """Tabel rekap per waktu makan (Pagi/Siang/Malam/Selingan + TOTAL).

    Kolom Jam diisi dari jam tiap item (bila tersedia); kalau item tidak
    membawa jam, dipakai rentang bawaan JAM_KATEGORI_WAKTU."""
    if df is None or df.empty or "Waktu" not in df.columns:
        return pd.DataFrame()
    urut_waktu = {"Pagi": 0, "Siang": 1, "Malam": 2, "Selingan": 3}
    kol_gizi = [g for g in pr.NAMA_GIZI if g in df.columns]
    jml = df.groupby("Waktu").size()
    out = df.groupby("Waktu", as_index=False)[kol_gizi].sum(numeric_only=True)
    out["Bahan"] = out["Waktu"].map(jml).astype(int)
    if "Jam" in df.columns and df["Jam"].notna().any():
        def _jam_baris(s):
            vals = sorted({
                str(x).strip().replace(":", ".")
                for x in s if str(x).strip() and str(x).strip().lower() != "nan"
            })
            return ", ".join(vals)
        jam_per_waktu = df.groupby("Waktu")["Jam"].apply(_jam_baris)
        out["Jam"] = out["Waktu"].map(jam_per_waktu).fillna("")
    else:
        out["Jam"] = out["Waktu"].map(JAM_KATEGORI_WAKTU).fillna("")
    out["_u"] = out["Waktu"].map(urut_waktu).fillna(99)
    out = out.sort_values("_u").drop(columns="_u").reset_index(drop=True)
    tot = {"Waktu": "TOTAL", "Jam": "", "Bahan": int(jml.sum())}
    for g in kol_gizi:
        tot[g] = float(df[g].sum())
    out = pd.concat([out, pd.DataFrame([tot])], ignore_index=True)
    for g in kol_gizi:
        out[g] = out[g].round(1)
    return out[["Waktu", "Jam", "Bahan"] + kol_gizi]


# ------------------------------------------------------------------
# HERO
# ------------------------------------------------------------------
_LOGO_RSPAL = Path(__file__).parent / "assets" / "logo_rspal.png"
_logo_b64 = (
    base64.b64encode(_LOGO_RSPAL.read_bytes()).decode()
    if _LOGO_RSPAL.exists() else ""
)
hero(
    "Artificial Intelligence-Based Dietary Recall &amp; Nutrition Assessment System",
    logo_b64=_logo_b64,
    org="Sub Departemen Gizi RSPAL dr. Ramelan",
    fitur=[
        ("🍚", f"{len(tkpi):,} Bahan TKPI"),
        ("🧪", "10 Zat Gizi"),
        ("⚡", "Energi &amp; Kebutuhan"),
        ("📤", "Export Excel/PDF"),
    ],
    ornamen=["🍎", "🥦", "🥛", "🍚", "🐟", "🥗"],
)

# ------------------------------------------------------------------
# Baris alat (pengganti panel kiri): info singkat + Reset input
# ------------------------------------------------------------------
alat_kiri, alat_kanan = st.columns([5, 1.2])
with alat_kiri:
    st.markdown(
        '<div class="info-blok">💾 Data diproses <b>lokal</b> di perangkat ini '
        '— aman & tidak dikirim ke internet.</div>',
        unsafe_allow_html=True,
    )
with alat_kanan:
    st.markdown("#### ")
    if st.button("🔄 Reset input", key="btn_reset_atas", width="stretch"):
        for k in list(st.session_state.keys()):
            if k.startswith("inp_") or k.startswith("del_") or k.startswith("ai_"):
                del st.session_state[k]
        st.session_state.inp_items = []
        st.session_state.menu_draft = []
        st.session_state.menu_log = []
        st.rerun()

tab_ai, tab_input, tab_bf, tab_file, tab_expor = st.tabs(
    ["🤖 Ketik Makanan (AI)", "🍽️ Input Recall", "📷 Buku Foto Porsi",
     "📊 Ringkasan File", "📤 Export"]
)

# ============================================================
# TAB AI — KETIK MAKANAN (pengenalan bahasa sehari-hari)
# ============================================================
with tab_ai:
    seksi("🤖 Ketik makanan — langsung jadi catatan")
    st.markdown(
        '<div class="info-blok">📝 <b>Cara pakai:</b> tulis makanan yang kamu '
        'makan (boleh pakai bahasa sehari-hari, misal <i>"pagi nasi 1 centong, '
        'telur dadar, teh manis"</i>) → klik <b>🔍 Kenali makanan ini</b> → '
        'cek hasilnya, pilih porsi yang sesuai, lalu klik '
        '<b>✅ Simpan</b>.</div>',
        unsafe_allow_html=True,
    )
    ai_teks = st.text_area(
        "✍️ Tulis makanan yang kamu makan (boleh bahasa sehari-hari):",
        placeholder="mis. pagi nasi 1 centong, telur dadar, teh manis. siang: ayam goreng 1 potong, sayur sop 1 mangkok, es teh manis",
        height=110, key="ai_teks",
    )
    if st.button("🔍 Kenali makanan ini", key="btn_ai_ubah", type="primary"):
        hasil = air.parse_recall(ai_teks, tkpi)
        st.session_state.ai_items = hasil
        for k in list(st.session_state.keys()):
            if k.startswith("ai_sel_") or k.startswith("ai_txt_") or k.startswith("ai_grm_") or k.startswith("ai_wkt_") or k.startswith("ai_bf_"):
                del st.session_state[k]
        st.rerun()

    ai_items = st.session_state.get("ai_items")
    if ai_items is None:
        st.markdown(
            '<div class="info-blok">✍️ Tulis makanan di kotak atas lalu '
            'klik <b>🔍 Kenali makanan ini</b>.</div>',
            unsafe_allow_html=True,
        )
    elif not ai_items:
        st.warning("Tidak ada makanan yang bisa dikenali dari teks itu. "
                   "Coba tulis lebih jelas, misal: 'pagi nasi 1 centong, telur dadar'.")
    else:
        st.markdown(air.ringkasan_cepat(ai_items))
        if len(ai_items) > 20:
            st.warning(f"Terlalu banyak item ({len(ai_items)}) — 20 item pertama saja "
                       "yang bisa ditambahkan sekaligus.")
            ai_items = ai_items[:20]
        # ---- tiap makanan: tampilan sederhana (nama + porsi + waktu) ----
        EMOJI_MAKANAN = [
            (("nasi", "bubur", "lontong", "ketupat", "jagung", "kentang", "ubi", "singkong",
              "roti", "mie", "bihun", "pasta"), "🍚"),
            (("ayam",), "🍗"), (("telur",), "🍳"), (("ikan", "cumi", "udang", "bandeng",
              "tongkol", "kembung", "lele", "nila", "tuna", "sarden", "teri"), "🐟"),
            (("tempe", "tahu", "kacang", "kacang", "tahu"), "🫘"),
            (("daging", "sapi", "kambing", "rendang", "empal", "bakso", "sate"), "🥩"),
            (("sayur", "bayam", "kangkung", "wortel", "buncis", "sop", "asem", "lodeh",
              "tumis", "urap", "gulai", "terong", "ketimun"), "🥬"),
            (("pisang", "mangga", "pepaya", "jeruk", "apel", "semangka", "melon", "nanas",
              "anggur", "salak", "rambutan", "duku", "jambu", "alpukat"), "🍎"),
            (("goreng", "kue", "donat", "bakwan", "risol", "pastel", "lemper", "lumpia",
              "martabak", "pempek", "singkong goreng", "ubi goreng"), "🍩"),
            (("teh",), "🍵"), (("kopi",), "☕"), (("susu",), "🥛"),
            (("jus", "minum", "sirup", "soda", "es"), "🥤"),
        ]

        def emoji_makanan(istilah: str) -> str:
            low = istilah.lower()
            for kata, emo in EMOJI_MAKANAN:
                if any(k in low for k in kata):
                    return emo
            return "🍽️"

        def gram_dari_opsi_porsi(val: str, gram_ai: float) -> float:
            mm = re.search(r"\(([\d.,]+)\s*g\)\s*$", val)
            if mm:
                return float(mm.group(1).replace(",", "."))
            return float(gram_ai)

        for i, it in enumerate(ai_items):
            st.markdown("---")
            # gram tebakan AI dipakai selama user belum memilih porsi/manual
            gram_ai = float(it["gram"]) if it.get("gram") else 100.0
            waktu_def = it["waktu"] if it["waktu"] in air.KATEGORI_WAKTU else "Pagi"
            kandidat = it["kandidat"] or []
            bahan_utama = kandidat[0] if kandidat else ""

            with st.container(border=True):
                # baris 1: nama makanan + info singkat
                kalori_preview = ""
                gram_efektif = float(st.session_state.get(f"ai_grm_{i}", gram_ai))
                if bahan_utama:
                    pr_h = reng.hitung_item(tkpi, bahan_utama, gram_efektif)
                    if pr_h:
                        kalori_preview = (f'<span style="float:right;font-size:12.5px;'
                                          f'color:#5F7A93">≈ {fmt(pr_h["zat"]["Energi"], 0)} '
                                          f'kkal</span>')
                st.markdown(
                    f'<div style="font-size:16px;font-weight:800;color:#10233F">'
                    f'{emoji_makanan(it["istilah"])} {it["istilah"]}</div>'
                    f'{kalori_preview}',
                    unsafe_allow_html=True,
                )
                if bahan_utama:
                    st.caption(f"Artinya: {bahan_utama} · berat & kalori mengikuti "
                               f"database TKPI")
                else:
                    st.caption("⚠️ Makanan ini belum cocok dengan database — "
                               "tulis nama bahannya di bawah.")

                # baris 2: pilihan porsi (utama) + waktu makan
                p1, p2 = st.columns([2.0, 1.2], vertical_alignment="bottom")
                with p1:
                    opsi_porsi = [f"✨ Sesuai teks ({gram_ai:g} g)"]
                    for c in bf.kumpul_porsi(KATALOG_BF, it["istilah"],
                                             max_item=2, max_porsi=4):
                        lab = f"{c['label']} · " if c["label"] != "-" else ""
                        opsi_porsi.append(f"📷 {c['ket']} ({c['gram']:g} g)")
                    opsi_porsi.append("✍️ Tulis gram sendiri…")
                    opsi_porsi = list(dict.fromkeys(opsi_porsi))  # buang duplikat

                    def _buat_pilih_porsi(idx: int, g_ai: float):
                        def _f() -> None:
                            val = st.session_state.get(f"ai_porsi_{idx}", "")
                            st.session_state[f"ai_grm_{idx}"] = \
                                gram_dari_opsi_porsi(val, g_ai)
                        return _f

                    cur = st.session_state.get(f"ai_porsi_{i}", "")
                    if cur not in opsi_porsi:
                        # cocokkan gram efektif ke opsi terdekat (default: sesuai teks)
                        if abs(gram_efektif - gram_ai) < 0.5:
                            cur = opsi_porsi[0]
                        else:
                            cur = opsi_porsi[0]
                            for o in opsi_porsi[1:-1]:
                                mm = re.search(r"\(([\d.,]+)\s*g\)\s*$", o)
                                if mm and abs(float(mm.group(1)) - gram_efektif) < 0.5:
                                    cur = o
                                    break
                    idx_porsi = opsi_porsi.index(cur) if cur in opsi_porsi else 0
                    st.selectbox(
                        "Porsi kamu (kalau lupa gram, tinggal pilih):",
                        opsi_porsi, index=idx_porsi, key=f"ai_porsi_{i}",
                        on_change=_buat_pilih_porsi(i, gram_ai),
                    )
                with p2:
                    idx_waktu = air.KATEGORI_WAKTU.index(waktu_def)
                    st.selectbox("Waktu makan", air.KATEGORI_WAKTU, index=idx_waktu,
                                 key=f"ai_wkt_{i}")

                # baris 3 (tersembunyi): bahan TKPI & gram manual — untuk ahli gizi
                with st.expander("⚙️ Ahli gizi: ganti bahan TKPI / gram manual"):
                    if kandidat:
                        pilihan_b = kandidat + ["✍️ Ketik manual…"]
                        st.selectbox(f"Bahan TKPI untuk '{it['istilah']}'",
                                     pilihan_b, key=f"ai_sel_{i}")
                        if st.session_state.get(f"ai_sel_{i}", "").startswith("✍️"):
                            st.text_input("Nama bahan (ketik manual)",
                                          value=it["istilah"], key=f"ai_txt_{i}")
                    else:
                        st.text_input("Nama bahan TKPI (cari di database)",
                                      value=it["istilah"], key=f"ai_txt_{i}")
                    if f"ai_grm_{i}" not in st.session_state:
                        st.session_state[f"ai_grm_{i}"] = gram_ai
                    st.number_input("Gram (g)", 1.0, 2000.0, step=5.0,
                                    key=f"ai_grm_{i}")

        if st.button(f"✅ Simpan {len(ai_items)} makanan ke catatan makan",
                     key="btn_ai_tambah", type="primary"):
            ok, gagal = 0, []
            for i, it in enumerate(ai_items):
                waktu = st.session_state.get(
                    f"ai_wkt_{i}", it["waktu"] if it["waktu"] in air.KATEGORI_WAKTU else "Pagi"
                )
                kandidat = it["kandidat"] or []
                if kandidat:
                    pilihan_sel = st.session_state.get(f"ai_sel_{i}", kandidat[0])
                    if pilihan_sel.startswith("✍️"):
                        bahan = st.session_state.get(f"ai_txt_{i}", "").strip()
                    else:
                        bahan = pilihan_sel
                else:
                    bahan = st.session_state.get(f"ai_txt_{i}", "").strip()
                if not bahan:
                    bahan = it["istilah"]
                gram = float(st.session_state.get(
                    f"ai_grm_{i}", float(it["gram"]) if it.get("gram") else 100.0
                ))
                if not bahan or gram <= 0:
                    gagal.append(it["istilah"])
                    continue
                hasil_hitung = reng.hitung_item(tkpi, bahan, gram)
                if hasil_hitung is None:
                    gagal.append(f"{it['istilah']} (bahan '{bahan}' tidak ada di TKPI)")
                    continue
                jam_def = JAM_BAWAAN_KATEGORI.get(waktu, datetime.time(7, 0))
                st.session_state.inp_items.append({
                    "waktu": waktu,
                    "jam": jam_def.strftime("%H:%M"),
                    "menu": it["istilah"],
                    **hasil_hitung,
                })
                ok += 1
            if ok:
                st.success(f"✅ {ok} makanan tersimpan. Buka tab 🍽️ Input Recall "
                           "untuk melihat total & capaiannya.")
            if gagal:
                st.warning("Tidak tersimpan: " + "; ".join(gagal[:5])
                           + (" …" if len(gagal) > 5 else ""))
            if not gagal:
                st.session_state.ai_items = []
                for k in list(st.session_state.keys()):
                    if (k.startswith("ai_sel_") or k.startswith("ai_txt_")
                            or k.startswith("ai_grm_") or k.startswith("ai_wkt_")
                            or k.startswith("ai_bf_") or k.startswith("ai_porsi_")):
                        del st.session_state[k]
                st.rerun()

# ============================================================
# TAB 1 — INPUT RECALL
# ============================================================
with tab_input:
    seksi("1️⃣ Data pasien & kebutuhan energi")
    k1, k2, k3, k4, k5 = st.columns([1, 1, 1, 1, 1.5])
    with k1:
        inp_jk = st.radio("Jenis kelamin", ["Perempuan", "Laki-laki"], horizontal=True, key="inp_jk")
    with k2:
        inp_umur = st.number_input("Usia (tahun)", 0, 120, 35, step=1, key="inp_umur")
    with k3:
        inp_bb = st.number_input("BB (kg)", 1.0, 300.0, 60.0, key="inp_bb")
    with k4:
        inp_tb = st.number_input("TB (cm)", 30.0, 250.0, 160.0, key="inp_tb")
    with k5:
        inp_akt = st.selectbox("Aktivitas", list(reng.FAKTOR_AKTIVITAS.keys()), key="inp_akt")
    with st.expander("🪪 Identitas tambahan (untuk laporan/simpan file)"):
        c1, c2, c3 = st.columns(3)
        with c1:
            inp_nama = st.text_input("Nama pasien", key="inp_nama")
        with c2:
            inp_diet = st.text_input("Jenis diet", key="inp_diet")
        with c3:
            inp_kons = st.text_input("Konsistensi", key="inp_kons")
        inp_rm = st.text_input("No RM / diagnosa", key="inp_rm")

    kbt = reng.kebutuhan_pasien(inp_jk, inp_umur, inp_bb, inp_tb, inp_akt)
    baris_kpi([
        dict(ikon="⚡", label="Energi", nilai=f'{fmt(kbt["Energi"], 0)} <small>kkal</small>',
             sub="Harris-Benedict × aktivitas", aksen=BIRU),
        dict(ikon="🥩", label="Protein (15%)", nilai=f'{fmt(kbt["Protein"], 0)} <small>g</small>',
             sub="≈ 15% dari energi", aksen=BIRU_MUDA),
        dict(ikon="🫒", label="Lemak (25%)", nilai=f'{fmt(kbt["Lemak"], 0)} <small>g</small>',
             sub="≈ 25% dari energi", aksen=BIRU_MUDA),
        dict(ikon="🌾", label="KH (60%)", nilai=f'{fmt(kbt["KH"], 0)} <small>g</small>',
             sub="≈ 60% dari energi", aksen=BIRU_MUDA),
    ])

    seksi("2️⃣ Masukkan makanan yang dikonsumsi")
    e1, e2, e3 = st.columns([1.5, 2.0, 1.2])
    with e1:
        inp_waktu = st.selectbox(
            "Waktu makan", ["Pagi", "Siang", "Malam", "Selingan"],
            key="inp_waktu", on_change=reset_jam_ikut_kategori,
        )
        if "inp_jam" not in st.session_state:
            st.session_state["inp_jam"] = JAM_BAWAAN_KATEGORI.get(
                inp_waktu, datetime.time(7, 0)
            )
        inp_jam = st.time_input(
            "Jam makan (bisa diedit)",
            key="inp_jam",
        )
        inp_menu = st.text_input("Nama hidangan (opsional)", key="inp_menu")
    with e2:
        inp_cari = st.text_input("🔎 Ketik nama bahan (mis. nasi, ayam, wortel)", key="inp_cari")
        daftar_nama = tkpi["Nama Bahan Makanan"].astype(str)
        pilihan_nama = (
            daftar_nama[daftar_nama.str.lower().str.contains(inp_cari.strip().lower(), na=False)]
            if inp_cari.strip() else daftar_nama
        )
        if len(pilihan_nama) > 200:
            pilihan_nama = pilihan_nama.head(200)
        st.caption(f"{len(pilihan_nama)} bahan cocok — pilih dari daftar:")
        inp_bahan = st.selectbox("Bahan", list(pilihan_nama), key="inp_bahan",
                                 on_change=lambda: st.session_state.pop("inp_urt", None))
        pra = reng.cari_bahan(tkpi, inp_bahan)
        if pra is not None:
            st.markdown(
                f'<div class="info-blok">⚡ {fmt(pra["Energi"], 0)} kkal · '
                f'Protein {fmt(pra["Protein"], 1)} g per 100 g · '
                f'BDD {fmt(pra["BDD"], 0)}%</div>',
                unsafe_allow_html=True,
            )
        # ---- Lupa gram? pilih porsi dari Buku Foto (gram terisi otomatis) ----
        daftar_urt = bf.kumpul_porsi(KATALOG_BF, inp_bahan, max_item=2, max_porsi=4)
        if daftar_urt:
            opsi_urt = [
                f"{c['ket']} ({c['gram']:g} g) · {c['nama']}" for c in daftar_urt
            ]

            def _isi_gram_urt() -> None:
                val = st.session_state.get("inp_urt", "")
                mm = re.search(r"\(([\d.,]+)\s*g\)\s*·", val)
                if mm:
                    st.session_state["inp_gram"] = float(mm.group(1).replace(",", "."))

            # kalau pilihan lama tidak ada di daftar porsi bahan baru -> pakai
            # porsi pertama & isi gram-nya langsung (sinkron sejak awal)
            cur_urt = st.session_state.get("inp_urt", "")
            if cur_urt not in opsi_urt:
                st.session_state["inp_urt"] = opsi_urt[0]
                mm0 = re.search(r"\(([\d.,]+)\s*g\)\s*·", opsi_urt[0])
                if mm0:
                    st.session_state["inp_gram"] = float(
                        mm0.group(1).replace(",", ".")
                    )
            idx_urt = opsi_urt.index(st.session_state["inp_urt"])
            st.selectbox(
                "📷 Lupa gram? Pilih porsi dari Buku Foto — gram terisi otomatis",
                opsi_urt, index=idx_urt, key="inp_urt", on_change=_isi_gram_urt,
            )
    with e3:
        if "inp_gram" not in st.session_state:
            st.session_state["inp_gram"] = 100.0
        inp_gram = st.number_input("Berat bahan (gram)", 0.0, 5000.0, step=10.0, key="inp_gram")
        st.markdown("#### ")
        if st.button("➕ Tambahkan", type="primary", key="btn_tambah", width="stretch"):
            hasil = reng.hitung_item(tkpi, inp_bahan, inp_gram)
            if hasil is None:
                st.error(f"Bahan '{inp_bahan}' tidak ditemukan di TKPI.")
            else:
                st.session_state.inp_items.append(
                    {
                        "waktu": inp_waktu,
                        "jam": inp_jam.strftime("%H:%M"),
                        "menu": inp_menu.strip() or "(tanpa menu)",
                        **hasil,
                    }
                )
                st.rerun()

    # ---- Ambil dari Master Menu (pilihan cepat) ----
    df_menu_lib = ms.baca_menu(MENU_FILE)
    nama_menu_lib = ms.daftar_nama_menu(df_menu_lib)
    if nama_menu_lib:
        st.markdown(
            '<div style="margin:14px 0 4px;font-size:15px;font-weight:800;color:#0A2E6E;'
            'padding-left:10px;border-left:4px solid #1565C0">⚡ Pilih dari Master Menu</div>',
            unsafe_allow_html=True,
        )
        q1, q2 = st.columns([3.4, 1.2])
        with q1:
            q_menu = st.selectbox("Menu tersimpan", nama_menu_lib, key="q_pilih_menu")
            baris_q = df_menu_lib[df_menu_lib["Menu"] == q_menu]
            tot_q = baris_q[pr.NAMA_GIZI].sum(numeric_only=True)
            st.caption(f"⚡ {fmt(tot_q['Energi'], 0)} kkal · 🥩 {fmt(tot_q['Protein'], 1)} g · "
                       f"🫒 {fmt(tot_q['Lemak'], 1)} g · 🌾 {fmt(tot_q['KH'], 1)} g "
                       f"({len(baris_q)} bahan) · dicatat {inp_waktu.lower()} pukul "
                       f"{inp_jam.strftime('%H.%M')}")
        with q2:
            st.markdown("#### ")
            if st.button("➕ Tambahkan menu", key="q_tambah_menu", width="stretch"):
                ok, gagal = 0, []
                for _, rr in baris_q.iterrows():
                    bb_val = float(rr["BB"]) if pd.notna(rr["BB"]) else 0.0
                    h = reng.hitung_item(tkpi, str(rr["Bahan"]), bb_val)
                    if h is not None:
                        st.session_state.inp_items.append(
                            {
                                "waktu": inp_waktu,
                                "jam": inp_jam.strftime("%H:%M"),
                                "menu": q_menu,
                                **h,
                            }
                        )
                        ok += 1
                    else:
                        gagal.append(str(rr["Bahan"]))
                if gagal:
                    st.warning("Beberapa bahan tidak ditemukan di TKPI aktif: "
                               + ", ".join(gagal))
                st.success(f"✅ {ok} bahan dari menu '{q_menu}' ditambahkan.")
                st.rerun()

    daftar_item = st.session_state.inp_items
    if daftar_item:
        seksi(f"3️⃣ Daftar makanan masuk — {len(daftar_item)} bahan")
        df_item = pd.DataFrame([
            {"Waktu": it["waktu"], "Jam": it.get("jam", ""), "Menu": it["menu"],
             "Bahan": it["bahan"], "BB (g)": it["bb"],
             **{g: round(it["zat"][g], 2) for g in pr.NAMA_GIZI}}
            for it in daftar_item
        ])
        st.dataframe(df_item, width="stretch", height=240, hide_index=True)
        for i, it in enumerate(daftar_item):
            jam_label = f" · {it['jam']}" if it.get("jam") else ""
            if st.button(f"🗑️ Hapus: {it['bahan']} ({it['waktu']}{jam_label})", key=f"del_{i}"):
                st.session_state.inp_items.pop(i)
                st.rerun()

        tot = total_input()
        seksi("4️⃣ Capaian terhadap kebutuhan")
        g1, g2 = st.columns(2)
        with g1:
            st.markdown(bilah_capaian("⚡", "Energi", tot["Energi"], kbt["Energi"], "kkal"),
                        unsafe_allow_html=True)
            st.markdown(bilah_capaian("🥩", "Protein", tot["Protein"], kbt["Protein"], "g"),
                        unsafe_allow_html=True)
        with g2:
            st.markdown(bilah_capaian("🫒", "Lemak", tot["Lemak"], kbt["Lemak"], "g"),
                        unsafe_allow_html=True)
            st.markdown(bilah_capaian("🌾", "Karbohidrat", tot["KH"], kbt["KH"], "g"),
                        unsafe_allow_html=True)

        st.markdown("")
        gkiri, gkanan = st.columns([3, 2])
        with gkiri:
            seksi("Total zat gizi")
            baris_kpi([
                dict(ikon="⚡", label="Energi", nilai=f'{fmt(tot["Energi"])} <small>kkal</small>', aksen=BIRU),
                dict(ikon="🥩", label="Protein", nilai=f'{fmt(tot["Protein"])} <small>g</small>', aksen=BIRU_MUDA),
                dict(ikon="🫒", label="Lemak", nilai=f'{fmt(tot["Lemak"])} <small>g</small>', aksen=BIRU_MUDA),
                dict(ikon="🌾", label="KH", nilai=f'{fmt(tot["KH"])} <small>g</small>', aksen=BIRU_MUDA),
            ])
        with gkanan:
            import plotly.express as px
            df_w = pd.DataFrame([{"Waktu": it["waktu"], **it["zat"]} for it in daftar_item])
            per_w = df_w.groupby("Waktu", as_index=False)[pr.NAMA_GIZI].sum()
            if len(per_w) > 1:
                fig = px.pie(per_w, names="Waktu", values="Energi", hole=0.5,
                             color_discrete_sequence=[BIRU_TUA, BIRU, BIRU_MUDA, "#90CAF9"])
                fig.update_traces(textinfo="percent+label", textfont_size=12)
                st.markdown('<div class="seksi">Kontribusi energi per waktu</div>',
                            unsafe_allow_html=True)
                st.plotly_chart(gaya_fig(fig), width="stretch")

        seksi("🕐 Rekap per waktu makan")
        df_wkt = pd.DataFrame([
            {"Waktu": it["waktu"], "Jam": it.get("jam", ""), **it["zat"]}
            for it in daftar_item
        ])
        if not df_wkt.empty:
            tbl_wkt = rekap_per_waktu_tabel(
                df_wkt[["Waktu", "Jam", "Energi", "Protein", "Lemak", "KH"]].copy()
            )
            if not tbl_wkt.empty:
                st.dataframe(tbl_wkt, width="stretch", hide_index=True)
                st.caption("Jam diambil dari jam makan yang dipilih saat menambah "
                           "makanan. Bahan = jumlah baris bahan pada waktu makan "
                           "tersebut; TOTAL = seluruh input recall.")

        seksi("5️⃣ Simpan / unduh")
        s1, s2 = st.columns(2)
        with s1:
            ident_hasil = {
                "Nama": inp_nama.strip(), "NO RM": inp_rm.strip(),
                "Usia": f"{inp_umur:g}", "Diagnosa": "",
                "Jenis Diet": inp_diet.strip(), "Konsistensi": inp_kons.strip(),
            }
            buf = reng.tulis_file_recall(tkpi, ident_hasil, daftar_item)
            st.download_button(
                "📥 Simpan sebagai Excel (format master)",
                data=buf.getvalue(),
                file_name=f"Recall_{inp_nama.strip() or 'pasien'}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_simpan_excel",
            )
            st.caption("Format sama dengan MASTER TKPI + Recall — bisa dibuka di Excel "
                       "atau di-upload kembali ke aplikasi ini.")
        with s2:
            if st.button("🖨️ Laporan PDF", key="btn_pdf_input"):
                try:
                    from reportlab.lib.pagesizes import A4
                    from reportlab.lib.units import mm
                    from reportlab.lib import colors
                    from reportlab.pdfgen import canvas
                    pdf_buf = io.BytesIO()
                    c = canvas.Canvas(pdf_buf, pagesize=A4)
                    tinggi = A4[1]
                    y = tinggi - 22 * mm
                    c.setFont("Helvetica-Bold", 14)
                    c.setFillColor(colors.HexColor(BIRU_TUA[1:]))
                    c.drawString(20 * mm, y, "Laporan Recall Gizi")
                    y -= 7 * mm
                    c.setFont("Helvetica", 10)
                    c.setFillColor(colors.black)
                    for lab, val in [("Nama", inp_nama), ("Usia", inp_umur), ("BB", inp_bb),
                                     ("TB", inp_tb), ("Jenis Diet", inp_diet)]:
                        if str(val).strip():
                            c.drawString(20 * mm, y, f"{lab}: {val}")
                            y -= 5 * mm
                    y -= 2 * mm
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(20 * mm, y, "Asupan vs Kebutuhan:")
                    y -= 5.5 * mm
                    c.setFont("Helvetica", 10)
                    for g in ["Energi", "Protein", "Lemak", "KH"]:
                        sat = "kkal" if g == "Energi" else "g"
                        tgt = kbt[g]
                        pct = tot[g] / tgt * 100 if tgt > 0 else 0
                        c.drawString(22 * mm, y, f"{g:<9} {fmt(tot[g])} {sat}   "
                                                 f"(kebutuhan {fmt(tgt, 0)} {sat}, {pct:.0f}%)")
                        y -= 5 * mm
                    c.showPage()
                    c.save()
                    pdf_buf.seek(0)
                    st.download_button("📥 Download PDF", pdf_buf.getvalue(),
                                       file_name="laporan_recall_input.pdf",
                                       mime="application/pdf", key="btn_dl_pdf_input")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Gagal membuat PDF: {exc}")
    else:
        st.markdown(
            '<div class="info-blok">Belum ada makanan. Cari bahan → pilih dari daftar → '
            'isi gram → klik <b>➕ Tambahkan</b>.</div>',
            unsafe_allow_html=True,
        )

# ============================================================
# TAB 2.5 — BUKU FOTO PORSI (URT untuk masyarakat)
# ============================================================
with tab_bf:
    seksi("📷 Pilih porsi dari Buku Foto Makanan")
    st.markdown(
        '<div class="info-blok">Foto porsi dari <b>Buku Foto Makanan '
        '(SKMI, Kemenkes)</b> — alat bantu wawancara recall: tunjukkan foto ke '
        'pasien, pilih porsi yang paling mirip (A/B/C), gram terisi otomatis, '
        'lalu zat gizi dihitung dari database TKPI.</div>',
        unsafe_allow_html=True,
    )
    if not KATALOG_BF:
        st.warning("Katalog buku foto belum tersedia (folder assets/buku_foto).")
    else:
        kiri_bf, kanan_bf = st.columns([1.0, 1.8], gap="large")
        with kiri_bf:
            opsi_kat = ["Semua kategori"] + [f"{k}. {bf.KATEGORI_NAMA[k]}" for k in "ABCDEFG"]
            bf_kat = st.selectbox("Kategori makanan", opsi_kat, key="bf_kat")
            kode_kat = bf_kat[0] if bf_kat != "Semua kategori" else ""
            bf_cari = st.text_input("🔎 Cari makanan…", key="bf_cari",
                                    placeholder="mis. nasi, ayam, sayur sop")
            daftar_bf = [
                it for it in KATALOG_BF
                if (not kode_kat or it["kategori"] == kode_kat)
                and (not bf_cari.strip() or bf_cari.strip().lower() in it["nama"].lower())
            ][:250]
            if not daftar_bf:
                st.info("Tidak ada makanan yang cocok. Coba kata lain.")
            else:
                def _fmt_bf(i: int) -> str:
                    it = daftar_bf[i]
                    n_gram = sum(1 for p in it["porsi"] if p.get("gram") is not None)
                    info = f" ({n_gram} porsi)" if n_gram else " (foto saja)"
                    return f'{it["nama"]}{info}'

                def _bf_ganti_item() -> None:
                    # ganti makanan -> gram mengikuti porsi pertama item baru
                    it = daftar_bf[st.session_state.get("bf_idx", 0)]
                    pg = [p for p in it["porsi"] if p.get("gram") is not None]
                    if pg:
                        st.session_state["bf_gram"] = float(pg[0]["gram"])
                    st.session_state.pop("bf_porsi", None)

                bf_idx = st.selectbox(
                    f"{len(daftar_bf)} makanan cocok — pilih:",
                    range(len(daftar_bf)), format_func=_fmt_bf, key="bf_idx",
                    on_change=_bf_ganti_item,
                )
                item_bf = daftar_bf[bf_idx]
                foto_bf = BASE_APP / item_bf["foto"]
                porsi_gram = [p for p in item_bf["porsi"] if p.get("gram") is not None]

                with kanan_bf:
                    st.markdown(
                        f'<div class="seksi">🍽️ {item_bf["nama"]}'
                        f'<span style="font-weight:600;font-size:12px;color:#5F7A93">'
                        f' — {bf.KATEGORI_NAMA.get(item_bf["kategori"], "")}</span></div>',
                        unsafe_allow_html=True,
                    )
                    if foto_bf.exists():
                        st.image(str(foto_bf), width="stretch")
                    st.caption("Foto asli buku: A/B/C = pilihan porsi dengan beratnya "
                               "masing-masing. Cocokkan dengan porsi pasien.")

                    if "bf_waktu" not in st.session_state:
                        st.session_state["bf_waktu"] = "Pagi"
                        st.session_state["bf_jam"] = JAM_BAWAAN_KATEGORI["Pagi"]

                    def _jam_ikut_waktu_bf() -> None:
                        kat = st.session_state.get("bf_waktu", "Pagi")
                        st.session_state["bf_jam"] = JAM_BAWAAN_KATEGORI.get(
                            kat, datetime.time(7, 0)
                        )

                    c1, c2 = st.columns(2)
                    with c1:
                        bf_waktu = st.selectbox(
                            "Waktu makan", ["Pagi", "Siang", "Malam", "Selingan"],
                            key="bf_waktu", on_change=_jam_ikut_waktu_bf,
                        )
                    with c2:
                        bf_jam = st.time_input("Jam makan", key="bf_jam")

                    # ---- pilihan porsi (kalau terbaca dari buku) ----
                    if porsi_gram:
                        def _fmt_porsi(p) -> str:
                            lab = f"{p['label']} · " if p["label"] != "-" else ""
                            return f"{lab}{p['ket']} = {p['gram']:g} g"

                        def _porsi_dipilih() -> None:
                            # saat pilihan porsi berubah -> gram ikut terisi
                            val = st.session_state.get("bf_porsi", "")
                            mm = re.search(r"=\s*([\d.,]+)\s*g$", val)
                            if mm:
                                st.session_state["bf_gram"] = float(
                                    mm.group(1).replace(",", ".")
                                )

                        bf_porsi = st.selectbox(
                            "Porsi dari foto (gram otomatis terisi)",
                            [_fmt_porsi(p) for p in porsi_gram],
                            key="bf_porsi", on_change=_porsi_dipilih,
                        )
                        gram_def = porsi_gram[0]["gram"]
                    else:
                        bf_porsi = None
                        gram_def = 100.0
                        st.caption("ℹ️ Keterangan porsi di halaman ini tidak terbaca "
                                   "otomatis — lihat foto & isi gram sesuai berat "
                                   "yang tertera di gambar.")

                    if "bf_gram" not in st.session_state:
                        st.session_state["bf_gram"] = float(gram_def)
                    st.number_input("Berat (gram)", 1.0, 3000.0,
                                    key="bf_gram", step=5.0)

                    # ---- bahan TKPI ----
                    istilah_tkpi = bf.cari_bahan_tkpi_dari_nama(item_bf["nama"])
                    kandidat_bahan = air.cari_kandidat(tkpi, istilah_tkpi, limit=8)
                    if kandidat_bahan:
                        pilihan_b = kandidat_bahan + ["✍️ Ketik manual…"]
                        def _fmt_b(i: int) -> str:
                            return pilihan_b[i]
                        bf_bahan_i = st.selectbox(
                            "Bahan di database TKPI", range(len(pilihan_b)),
                            format_func=_fmt_b, key="bf_bahan_i",
                        )
                        bahan_bf = pilihan_b[bf_bahan_i]
                        if bahan_bf.startswith("✍️"):
                            bahan_bf = st.text_input("Nama bahan (manual)", key="bf_bahan_manual")
                        else:
                            pra_bf = reng.cari_bahan(tkpi, bahan_bf)
                            if pra_bf is not None:
                                st.caption(
                                    f'⚡ {fmt(pra_bf["Energi"], 0)} kkal · Protein '
                                    f'{fmt(pra_bf["Protein"], 1)} g per 100 g · '
                                    f'BDD {fmt(pra_bf["BDD"], 0)}%'
                                )
                    else:
                        st.caption("⚠️ Nama ini tidak cocok dengan bahan TKPI — "
                                   "ketik manual (bisa makanan campuran).")
                        bahan_bf = st.text_input("Nama bahan (manual)", key="bf_bahan_manual")

                    if st.button("➕ Tambahkan ke daftar recall", key="bf_tambah",
                                 type="primary", width="stretch"):
                        gram_bf = float(st.session_state.get("bf_gram", 100.0))
                        if not bahan_bf or not str(bahan_bf).strip():
                            st.error("Pilih/isi dulu nama bahannya.")
                        else:
                            hasil_bf = reng.hitung_item(tkpi, str(bahan_bf).strip(), gram_bf)
                            if hasil_bf is None:
                                st.error(f"Bahan '{bahan_bf}' tidak ditemukan di TKPI.")
                            else:
                                st.session_state.inp_items.append({
                                    "waktu": bf_waktu,
                                    "jam": bf_jam.strftime("%H:%M"),
                                    "menu": item_bf["nama"],
                                    **hasil_bf,
                                })
                                st.success(f"✅ {item_bf['nama']} — {bahan_bf} "
                                           f"{gram_bf:g} g ditambahkan ke recall.")
                                st.rerun()

# ============================================================
# TAB 2 — RINGKASAN FILE
# ============================================================
with tab_file:
    # Data recall aktif di tab ini (file contoh bawaan, bisa diganti file upload
    # dan bisa dihapus barisnya oleh pengguna)
    if "file_items" not in st.session_state:
        st.session_state.file_items = items_file.copy()
        st.session_state.file_ident = dict(identitas_file)
        st.session_state.file_masalah = list(recall.get("masalah", []))
        st.session_state.file_sumber = "file contoh bawaan"
    items_v = st.session_state.file_items
    ident_v = st.session_state.file_ident
    masalah_v = st.session_state.file_masalah
    with st.expander("📂 Buka file recall pasien lain (opsional)"):
        up_p = st.file_uploader(
            "Pilih file hasil simpan / file MASTER TKPI + Recall pasien",
            type=["xlsx", "xls"], key="up_pasien",
        )
        if up_p is not None:
            dp = muat_data(up_p.getvalue())
            if dp.get("ok"):
                st.session_state.file_items = dp["recall"]["data"]
                st.session_state.file_ident = dp["recall"]["identitas"]
                st.session_state.file_masalah = list(dp["recall"].get("masalah", []))
                st.session_state.file_sumber = up_p.name
                st.success(f"✅ Memakai file: {up_p.name}")
            else:
                st.error(f"❌ {dp.get('pesan')}")

    if items_v.empty:
        st.warning("Sheet RECALL belum berisi data makanan.")
    else:
        ada_nama = any(str(ident_v.get(k, "")).strip() for k in ("Nama", "NO RM"))
        if ada_nama:
            seksi("Identitas pasien (dari file)")
            baris_kpi([
                dict(ikon="👤", label="Nama", nilai=f'<small style="font-size:15px">{ident_v.get("Nama") or "-"}</small>', aksen=BIRU),
                dict(ikon="🪪", label="No RM", nilai=f'<small style="font-size:15px">{ident_v.get("NO RM") or "-"}</small>', aksen=BIRU_MUDA),
                dict(ikon="🎂", label="Usia", nilai=f'<small style="font-size:15px">{ident_v.get("Usia") or "-"}</small>', aksen=BIRU_MUDA),
                dict(ikon="🏥", label="Diagnosa", nilai=f'<small style="font-size:15px">{ident_v.get("Diagnosa") or "-"}</small>', aksen=BIRU_MUDA),
                dict(ikon="🥗", label="Jenis Diet", nilai=f'<small style="font-size:15px">{ident_v.get("Jenis Diet") or "-"}</small>', aksen=BIRU_MUDA),
                dict(ikon="🍚", label="Konsistensi", nilai=f'<small style="font-size:15px">{ident_v.get("Konsistensi") or "-"}</small>', aksen=BIRU_MUDA),
            ])
        else:
            st.markdown('<div class="info-blok">ℹ️ Identitas pasien di file ini masih kosong '
                        '(file contoh) — isi di sheet RECALL untuk pasien sungguhan.</div>',
                        unsafe_allow_html=True)
        for pesan in masalah_v:
            st.warning(f"⚠️ {pesan}")

        total_f = pr.total_asupan(items_v)
        seksi("Total asupan (dari file)")
        baris_kpi([
            dict(ikon="⚡", label="Energi", nilai=f'{fmt(total_f["Energi"])} <small>kkal</small>', aksen=BIRU),
            dict(ikon="🥩", label="Protein", nilai=f'{fmt(total_f["Protein"])} <small>g</small>', aksen=BIRU_MUDA),
            dict(ikon="🫒", label="Lemak", nilai=f'{fmt(total_f["Lemak"])} <small>g</small>', aksen=BIRU_MUDA),
            dict(ikon="🌾", label="Karbohidrat", nilai=f'{fmt(total_f["KH"])} <small>g</small>', aksen=BIRU_MUDA),
        ])

        per_waktu = pr.rekap_per_waktu(items_v)
        if not per_waktu.empty:
            import plotly.graph_objects as go
            fig = go.Figure()
            warna_trace = [BIRU_TUA, BIRU, BIRU_MUDA, "#90CAF9", "#64B5F6"]
            for i, gizi in enumerate(["Energi", "Protein", "Lemak", "KH"]):
                fig.add_trace(go.Bar(name=gizi, x=per_waktu["Waktu"], y=per_waktu[gizi],
                                     marker_color=warna_trace[i % len(warna_trace)]))
            fig.update_layout(barmode="group", title="Zat gizi per waktu makan (file)",
                              legend=dict(orientation="h", y=1.1, x=0))
            st.plotly_chart(gaya_fig(fig), width="stretch")
        with st.expander("📋 Rincian bahan (dari file) — bisa hapus baris"):
            if items_v.empty:
                st.info("Belum ada data bahan. Buka file recall pasien di atas, "
                        "atau isi recall lewat tab Input Recall lalu simpan sebagai Excel.")
            else:
                df_r = items_v.copy()
                for g in pr.NAMA_GIZI:
                    if g in df_r.columns:
                        df_r[g] = df_r[g].round(2)
                pilih = df_r.copy()
                pilih.insert(0, "☑️ Hapus?", False)
                kolom_tetap = [c for c in pilih.columns if c != "☑️ Hapus?"]
                diedit = st.data_editor(
                    pilih, width="stretch", height=280, hide_index=True,
                    disabled=kolom_tetap, key="editor_hapus_file",
                )
                h1, h2, h3 = st.columns([1.3, 1.3, 2.6])
                with h1:
                    if st.button("🗑️ Hapus baris terpilih", key="btn_hapus_file",
                                 type="primary", width="stretch"):
                        n = int(diedit["☑️ Hapus?"].sum()) if diedit is not None else 0
                        if n > 0:
                            sisa = diedit[~diedit["☑️ Hapus?"]].drop(
                                columns=["☑️ Hapus?"]
                            ).reset_index(drop=True)
                            st.session_state.file_items = sisa
                            st.session_state.pop("editor_hapus_file", None)
                            st.success(f"✅ {n} baris dihapus.")
                            st.rerun()
                        else:
                            st.warning("Centang dulu baris yang mau dihapus (kolom ☑️ Hapus?).")
                with h2:
                    if st.button("🧹 Hapus semua data", key="btn_hapus_semua_file",
                                 width="stretch"):
                        st.session_state.file_items = items_v.iloc[0:0].copy()
                        st.session_state.pop("editor_hapus_file", None)
                        st.rerun()
                with h3:
                    st.caption(f"Sumber: {st.session_state.file_sumber} · "
                               f"{len(items_v)} baris tampil — hapus hanya mengubah "
                               "tampilan sesi ini, file asli tidak diubah.")

# ============================================================
# TAB 4 — EXPORT
# ============================================================
with tab_expor:
    daftar_ekspor = st.session_state.inp_items
    if daftar_ekspor:
        tot_e = total_input()
        st.markdown(f'<div class="info-blok">🍽️ <b>Input recall:</b> {len(daftar_ekspor)} bahan · '
                    f'Energi {fmt(tot_e["Energi"])} kkal · '
                    f'Protein {fmt(tot_e["Protein"])} g</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-blok">🍽️ Belum ada input recall di tab 1.</div>',
                    unsafe_allow_html=True)
    if not items_file.empty:
        total_f = pr.total_asupan(items_file)
        buf_f = io.BytesIO()
        with pd.ExcelWriter(buf_f, engine="openpyxl") as penulis:
            pd.DataFrame({"Keterangan": list(identitas_file.keys()),
                          "Nilai": list(identitas_file.values())}).to_excel(
                penulis, index=False, sheet_name="Identitas")
            pd.DataFrame({"Zat Gizi": pr.NAMA_GIZI,
                          "Total": [round(float(total_f[g]), 2) for g in pr.NAMA_GIZI],
                          "Satuan": [reng.SATUAN[g] for g in pr.NAMA_GIZI]}).to_excel(
                penulis, index=False, sheet_name="Total Asupan")
            pw = pr.rekap_per_waktu(items_file)
            for g in pr.NAMA_GIZI:
                pw[g] = pw[g].round(2)
            pw.to_excel(penulis, index=False, sheet_name="Per Waktu Makan")
            df_rit = items_file.copy()
            for g in pr.NAMA_GIZI:
                df_rit[g] = df_rit[g].round(2)
            df_rit.to_excel(penulis, index=False, sheet_name="Rincian Bahan")
        st.download_button("📥 Ringkasan file → Excel (.xlsx)", data=buf_f.getvalue(),
                           file_name="ringkasan_recall.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_ringkas_file")
        st.download_button("📥 Rincian file → CSV", data=items_file.to_csv(index=False).encode("utf-8-sig"),
                           file_name="rincian_recall.csv", mime="text/csv", key="dl_csv_file")

st.markdown('<div class="footer-app">Aplikasi Recall Gizi · data diproses lokal di perangkat '
            'Anda · dibuat oleh Sub Departemen Gizi RSPAL dr. Ramelan · © 2026</div>', unsafe_allow_html=True)
