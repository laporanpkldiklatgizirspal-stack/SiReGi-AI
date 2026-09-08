"""
Aplikasi MASTER TKPI — penjelajah database bahan makanan
=========================================================
Fungsi: buka file master (sheet REKAP BAHAN MAKANAN / DATABASE TKPI),
cari bahan, lihat detail zat gizi per 100 g, bandingkan beberapa bahan.

Jalankan:  streamlit run app_master.py --server.port 8502
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import parser_recall as pr
from utils import master_writer as mw
from utils import menu_store as ms
from utils import recall_engine as reng
from utils import gate_login as gl

FILE_BAWAAN = Path(__file__).parent / "data" / "MASTER_TKPI__Recall.xlsx"
MENU_FILE = Path(__file__).parent / "data" / "MENU_GIZI.xlsx"

BIRU_TUA = "#0A2E6E"
BIRU = "#1565C0"
BIRU_MUDA = "#42A5F5"
TEKS = "#10233F"
ABU = "#5F7A93"

IKON_GIZI = {
    "Energi": "⚡", "Protein": "🥩", "Lemak": "🫒", "KH": "🌾", "Serat": "🥦",
    "Ca": "🦴", "Fe": "🩸", "Na": "🧂", "K": "🍌", "Vit. C": "🍊",
}
SATUAN = {"Energi": "kkal", "Protein": "g", "Lemak": "g", "KH": "g", "Serat": "g",
          "Ca": "mg", "Fe": "mg", "Na": "mg", "K": "mg", "Vit. C": "mg"}

st.set_page_config(page_title="Master TKPI", page_icon="📖", layout="wide",
                   initial_sidebar_state="expanded")

CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif; }}
  .stApp {{
    background: radial-gradient(1100px 460px at 88% -8%, #EAF1FB 0%, rgba(234,241,251,0) 60%),
               linear-gradient(180deg, #F7FAFD 0%, #F2F7FC 100%);
  }}
  [data-testid="stHeader"] {{ background: transparent; }}
  [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #FFFFFF 0%, #F4F8FD 100%);
    border-right: 1px solid #E3ECF6;
  }}
  .sisi-logo {{
    background: linear-gradient(135deg, {BIRU_TUA} 0%, {BIRU} 100%);
    border-radius: 16px; padding: 14px; margin-bottom: 10px; color: #fff;
    box-shadow: 0 6px 18px rgba(21,101,192,.25);
  }}
  .sisi-logo .sisi-judul {{ font-size: 18px; font-weight: 800; }}
  .sisi-logo .sisi-sub {{ font-size: 11.5px; opacity: .85; margin-top: 2px; }}
  .sisi-chip {{
    background: #fff; border: 1px solid #E3ECF6; border-radius: 10px;
    padding: 7px 10px; margin-top: 6px; font-size: 12px; color: {TEKS};
  }}
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
    content: "📖"; position: absolute; left: 24px; bottom: -10px; font-size: 120px;
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
  @media (max-width: 640px) {{
    .hero {{ padding: 28px 18px 24px; }}
    .hero h1 {{ font-size: 23px; }}
    .hero .hero-org {{ font-size: 11px; letter-spacing: .8px; padding: 5px 12px; }}
    .hero .hero-logo {{ height: 84px; }}
  }}
  .seksi {{
    font-size: 15px; font-weight: 800; color: {BIRU_TUA}; margin: 18px 0 10px;
    padding-left: 10px; border-left: 4px solid {BIRU};
  }}
  .kartu-bahan {{
    background: linear-gradient(135deg, #FFFFFF, #F2F7FC);
    border: 1px solid #DCE8F5; border-radius: 16px; padding: 16px 18px;
    box-shadow: 0 4px 14px rgba(16,35,63,.07);
  }}
  .kartu-bahan .nama {{ font-size: 20px; font-weight: 800; color: {BIRU_TUA}; }}
  .kartu-bahan .sub {{ font-size: 12px; color: {ABU}; margin-top: 2px; }}
  .mini {{
    background: #fff; border: 1px solid #E3ECF6; border-radius: 12px;
    padding: 8px 10px; text-align: center; height: 100%;
    box-shadow: 0 1px 4px rgba(16,35,63,.04);
  }}
  .mini .mini-ico {{ font-size: 15px; }}
  .mini .mini-lab {{ font-size: 10px; font-weight: 700; color: {ABU};
    text-transform: uppercase; letter-spacing: .3px; }}
  .mini .mini-val {{ font-size: 16px; font-weight: 800; color: {TEKS}; line-height: 1.3; }}
  .mini .mini-val small {{ font-size: 10px; color: {ABU}; font-weight: 600; }}
  .stTextInput input, .stSelectbox [data-baseweb="select"] > div {{
    border-radius: 10px !important; border: 1px solid #D7E3F0 !important; background: #fff !important;
  }}
  .stButton > button {{
    border-radius: 10px !important; font-weight: 700 !important; border: none !important;
    box-shadow: 0 3px 10px rgba(21,101,192,.18);
  }}
  .stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {BIRU_TUA}, {BIRU}) !important; color: #fff !important;
  }}
  .stDownloadButton > button {{
    background: #fff !important; color: {BIRU} !important;
    border: 1.5px solid {BIRU} !important; border-radius: 10px !important; font-weight: 700 !important;
  }}
  [data-baseweb="tab-list"] {{ gap: 6px; background: #fff; padding: 6px; border-radius: 14px;
    border: 1px solid #E3ECF6; margin-bottom: 14px; }}
  [data-baseweb="tab"] {{ font-weight: 700; font-size: 14px; border-radius: 10px; padding: 8px 16px; }}
  [data-baseweb="tab"][aria-selected="true"] {{
    background: linear-gradient(135deg, {BIRU_TUA}, {BIRU}) !important; color: #fff !important; }}
  [data-baseweb="tab-highlight"] {{ display: none; }}
  [data-testid="stDataFrame"] {{
    border: 1px solid #E3ECF6 !important; border-radius: 12px !important; overflow: hidden;
  }}
  .footer-app {{ text-align: center; color: {ABU}; font-size: 11.5px; margin-top: 26px;
    padding-top: 12px; border-top: 1px dashed #D7E3F0; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------- GERBANG LOGIN (username & password) ----------------
if not gl.tampilkan_login():
    st.stop()
gl.tombol_keluar(sidebar=True)


def hero(judul: str, sub: str, lencana: list[str] | None = None,
         logo_b64: str = "", org: str = ""):
    logo = (
        '<img class="hero-logo" src="data:image/png;base64,' + logo_b64
        + '" alt="RSPAL dr. Ramelan"/>'
    ) if logo_b64 else ""
    org_html = f'<div class="hero-org">{org}</div>' if org else ""
    chip = "".join(f'<span class="lencana">{b}</span>' for b in (lencana or []))
    st.markdown(
        f'<div class="hero">{logo}<h1>{judul}</h1>{org_html}<p>{sub}</p>{chip}</div>',
        unsafe_allow_html=True,
    )


def seksi(judul: str):
    st.markdown(f'<div class="seksi">{judul}</div>', unsafe_allow_html=True)


def fmt(v, desimal: int = 1) -> str:
    try:
        if pd.isna(v):
            return "-"
        return f"{float(v):,.{desimal}f}"
    except Exception:  # noqa: BLE001
        return "-"


def gaya_fig(fig):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Plus Jakarta Sans, Segoe UI", color=TEKS),
                      margin=dict(l=10, r=10, t=40, b=10))
    return fig


@st.cache_data(show_spinner="Membaca file master...")
def muat_master(sumber, mtime: float = 0.0) -> pd.DataFrame:
    """mtime dipakai supaya cache otomatis baca ulang bila file master disimpan."""
    if isinstance(sumber, bytes):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(sumber)
            tmp = f.name
        try:
            return pr.baca_tkpi(tmp)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return pr.baca_tkpi(sumber)


# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(
        f'<div class="sisi-logo"><div class="sisi-judul">📖 Master TKPI</div>'
        f'<div class="sisi-sub">Database bahan makanan</div></div>',
        unsafe_allow_html=True,
    )
    up = st.file_uploader("Upload file master (.xlsx)", type=["xlsx", "xls"], key="up_master")
    try:
        if up is not None:
            tkpi = muat_master(up.getvalue())
            nama_file = up.name
        else:
            if not FILE_BAWAAN.exists():
                st.error("File master bawaan tidak ditemukan.")
                st.stop()
            tkpi = muat_master(str(FILE_BAWAAN), os.path.getmtime(FILE_BAWAAN))
            nama_file = FILE_BAWAAN.name
        tkpi_ok = True
    except Exception as exc:  # noqa: BLE001
        tkpi_ok = False
        st.error(f"❌ Gagal membaca: {exc}")

    if tkpi_ok:
        st.markdown(
            f'<div class="sisi-chip">📄 <b>{nama_file}</b></div>'
            f'<div class="sisi-chip">📦 Bahan: <b>{len(tkpi):,}</b></div>'
            f'<div class="sisi-chip">🧪 Zat gizi: <b>10</b> (per 100 g)</div>',
            unsafe_allow_html=True,
        )

if not tkpi_ok:
    st.stop()

# Gabungkan bahan yang ditambahkan pada sesi ini (mode file upload)
if "pending_bahan" not in st.session_state:
    st.session_state.pending_bahan = []
if "nama_baru" not in st.session_state:
    st.session_state.nama_baru = []
if st.session_state.pending_bahan:
    tkpi = pd.concat([tkpi, pd.DataFrame(st.session_state.pending_bahan)], ignore_index=True)

# ---------------- HERO ----------------
_LOGO_RSPAL = Path(__file__).parent / "assets" / "logo_rspal.png"
_logo_b64 = (
    base64.b64encode(_LOGO_RSPAL.read_bytes()).decode()
    if _LOGO_RSPAL.exists() else ""
)
hero(
    "Master TKPI — Food Composition &amp; Menu Management System",
    "Penjelajah database bahan makanan (TKPI): cari bahan, lihat kandungan zat gizi "
    "per 100 g bagian dapat dimakan (BDD), kelola master menu, dan bandingkan beberapa "
    "bahan sekaligus.",
    [f"{len(tkpi):,} bahan", "10 zat gizi", "Nilai per 100 g + BDD"],
    logo_b64=_logo_b64,
    org="Sub Departemen Gizi RSPAL dr. Ramelan",
)

cari = st.text_input("🔎 Cari nama bahan (mis. ayam, beras, tempe, wortel)", key="cari_master")

hasil = tkpi
if cari.strip():
    hasil = tkpi[tkpi["Nama Bahan Makanan"].str.lower().str.contains(cari.lower(), na=False)]
st.caption(f"Menemukan **{len(hasil):,} bahan**" + (f" untuk kata '{cari.strip()}'" if cari.strip() else " — ketik kata kunci untuk mencari"))

tab_cari, tab_tambah, tab_menu, tab_tabel, tab_banding = st.tabs(
    ["🔍 Cari & Detail", "➕ Tambah Bahan", "🍱 Master Menu",
     "📋 Tabel Lengkap", "⚖️ Bandingkan Bahan"]
)

# ============ TAB 1: CARI & DETAIL ============
with tab_cari:
    if hasil.empty:
        st.warning("Tidak ada bahan yang cocok.")
    else:
        daftar_pilih = list(hasil["Nama Bahan Makanan"])
        if len(daftar_pilih) > 500:
            daftar_pilih = daftar_pilih[:500]
            st.caption("Pencarian terlalu luas — daftar dibatasi 500 bahan. Persempit kata kunci.")
        nama_pilih = st.selectbox("Pilih bahan untuk dilihat detailnya", daftar_pilih, key="pilih_bahan")
        baris = hasil[hasil["Nama Bahan Makanan"] == nama_pilih].iloc[0]

        bdd = baris["BDD"] if pd.notna(baris["BDD"]) else 100.0
        st.markdown(
            f'<div class="kartu-bahan">'
            f'<div class="nama">🥗 {baris["Nama Bahan Makanan"]}</div>'
            f'<div class="sub">Kandungan zat gizi per 100 gram bagian yang dapat dimakan · '
            f'BDD <b>{fmt(bdd, 0)}%</b></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("")
        mini = []
        for g in pr.NAMA_GIZI:
            mini.append(f'<div class="mini"><div class="mini-ico">{IKON_GIZI[g]}</div>'
                        f'<div class="mini-lab">{g}</div>'
                        f'<div class="mini-val">{fmt(baris[g], 0)} <small>{SATUAN[g]}</small></div></div>')
        cols = st.columns(5)
        for i, blok in enumerate(mini):
            with cols[i % 5]:
                st.markdown(blok, unsafe_allow_html=True)
            if i % 5 == 4:
                cols = st.columns(5)

# ============ TAB 2: TAMBAH BAHAN ============
with tab_tambah:
    if up is None:
        st.markdown(
            f'<div style="background:#fff;border:1px solid #E3ECF6;border-radius:12px;'
            f'padding:10px 14px;font-size:13px;color:#5F7A93">💾 Mode saat ini: menambah '
            f'LANGSUNG ke file master bawaan <b>{nama_file}</b>. Bahan baru otomatis '
            f'dipakai juga oleh aplikasi Recall Gizi.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#FFF8E6;border:1px solid #F2E2B3;border-radius:12px;'
            'padding:10px 14px;font-size:13px;color:#7A5B00">⚠️ Karena file master di-upload '
            '(bukan file bawaan), bahan baru ditambahkan **sementara** di sesi ini. '
            'Gunakan tombol **Download master + bahan baru** di bawah, lalu simpan file-nya '
            'sebagai pengganti master.</div>',
            unsafe_allow_html=True,
        )

    seksi("Formulir bahan makanan baru")
    nama_baru = st.text_input("Nama bahan makanan * (cth: Pisang ambon, segar)", key="tb_nama")

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        v_energi = st.number_input("⚡ Energi (kkal) *", 0.0, 900.0, 0.0, step=1.0, key="tb_energi")
    with k2:
        v_protein = st.number_input("🥩 Protein (g)", 0.0, 100.0, 0.0, step=0.1, key="tb_protein")
    with k3:
        v_lemak = st.number_input("🫒 Lemak (g)", 0.0, 100.0, 0.0, step=0.1, key="tb_lemak")
    with k4:
        v_kh = st.number_input("🌾 KH (g)", 0.0, 100.0, 0.0, step=0.1, key="tb_kh")
    with k5:
        v_serat = st.number_input("🥦 Serat (g)", 0.0, 100.0, 0.0, step=0.1, key="tb_serat")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        v_ca = st.number_input("🦴 Kalsium Ca (mg)", 0.0, 2000.0, 0.0, step=1.0, key="tb_ca")
    with m2:
        v_fe = st.number_input("🩸 Zat besi Fe (mg)", 0.0, 100.0, 0.0, step=0.1, key="tb_fe")
    with m3:
        v_na = st.number_input("🧂 Natrium Na (mg)", 0.0, 5000.0, 0.0, step=1.0, key="tb_na")
    with m4:
        v_k = st.number_input("🍌 Kalium K (mg)", 0.0, 5000.0, 0.0, step=1.0, key="tb_k")
    with m5:
        v_vitc = st.number_input("🍊 Vitamin C (mg)", 0.0, 500.0, 0.0, step=0.1, key="tb_vitc")

    st.caption("Nilai di atas adalah kandungan **per 100 gram** bahan. Kosongkan dengan 0 bila tidak diketahui.")
    bdd_baru = st.number_input("BDD — bagian yang dapat dimakan (%)", 0.0, 100.0, 100.0, step=1.0, key="tb_bdd")

    zat_baru = {
        "Energi": v_energi, "Protein": v_protein, "Lemak": v_lemak, "KH": v_kh,
        "Serat": v_serat, "Ca": v_ca, "Fe": v_fe, "Na": v_na, "K": v_k, "Vit. C": v_vitc,
    }

    if st.button("💾 Simpan bahan baru ke master", type="primary", key="tb_simpan", width="stretch"):
        nama_bersih = nama_baru.strip()
        if not nama_bersih:
            st.error("❌ Nama bahan wajib diisi.")
        elif v_energi <= 0 and v_protein <= 0 and v_kh <= 0:
            st.error("❌ Minimal isi Energi ATAU Protein/KH (tidak boleh semuanya 0).")
        elif mw.bahan_duplikat(tkpi, nama_bersih):
            st.error(f"❌ Bahan '{nama_bersih}' sudah ada di database master.")
        else:
            if up is None:
                try:
                    mw.tambah_bahan_ke_file(str(FILE_BAWAAN), nama_bersih, zat_baru, bdd_baru)
                    st.session_state.nama_baru.append(nama_bersih)
                    st.cache_data.clear()
                    st.success(f"✅ '{nama_bersih}' tersimpan ke file master.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"❌ Gagal menyimpan: {exc}")
            else:
                row_baru = {"Nama Bahan Makanan": nama_bersih}
                for g in pr.NAMA_GIZI:
                    row_baru[g] = zat_baru[g]
                row_baru["BDD"] = bdd_baru
                st.session_state.pending_bahan.append(row_baru)
                st.session_state.nama_baru.append(nama_bersih)
                st.rerun()

    if st.session_state.nama_baru:
        seksi("Baru ditambahkan sesi ini")
        st.markdown(" &nbsp; ".join(
            f'<span style="background:#EAF1FB;border:1px solid #C9DCF2;border-radius:20px;'
            f'padding:3px 12px;font-size:12px;color:#0A2E6E;display:inline-block;margin:2px">✅ {n}</span>'
            for n in st.session_state.nama_baru[-12:]
        ), unsafe_allow_html=True)

    if up is not None and st.session_state.pending_bahan:
        seksi("Download master hasil tambahan")
        df_gabung = tkpi.copy()
        for g in pr.NAMA_GIZI + ["BDD"]:
            df_gabung[g] = pd.to_numeric(df_gabung[g], errors="coerce")
        buf_baru = mw.df_ke_file_master(df_gabung)
        st.download_button(
            "📥 Download master + bahan baru (.xlsx)",
            data=buf_baru.getvalue(),
            file_name="MASTER_TKPI_baru.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption("File ini berisi seluruh bahan (termasuk yang baru). Simpan sebagai "
                   "pengganti master, atau upload kembali ke aplikasi ini.")

# ============ TAB 3: MASTER MENU ============
with tab_menu:
    st.markdown(
        '<div style="background:#fff;border:1px solid #E3ECF6;border-radius:12px;'
        'padding:10px 14px;font-size:13px;color:#5F7A93">🍱 Susun <b>menu</b> dari berbagai '
        'bahan (dengan beratnya). Menu tersimpan menjadi <b>pilihan cepat</b> saat input '
        'recall pasien di aplikasi Recall Gizi.</div>',
        unsafe_allow_html=True,
    )
    if "mm_draft" not in st.session_state:
        st.session_state.mm_draft = []
    if "mm_log" not in st.session_state:
        st.session_state.mm_log = []

    kol_kiri, kol_kanan = st.columns([1.3, 1])
    with kol_kiri:
        seksi("Buat menu baru")
        mm_nama = st.text_input("Nama menu * (cth: Menu Diet DM Siang A)", key="mm_nama")

        p1, p2, p3 = st.columns([1.1, 2.2, 1.2])
        with p1:
            mm_gram = st.number_input("Berat (gram)", 0.0, 5000.0, 100.0, step=10.0, key="mm_gram")
        with p2:
            mm_cari = st.text_input("🔎 Cari bahan", key="mm_cari")
            daftar_mm = tkpi["Nama Bahan Makanan"].astype(str)
            if mm_cari.strip():
                daftar_mm = daftar_mm[daftar_mm.str.lower().str.contains(mm_cari.lower(), na=False)]
            if len(daftar_mm) > 200:
                daftar_mm = daftar_mm.head(200)
            mm_bahan = st.selectbox("Bahan", list(daftar_mm), key="mm_bahan")
        with p3:
            st.markdown("#### ")
            if st.button("➕ Masukkan", key="mm_tambah", width="stretch"):
                hasil = reng.hitung_item(tkpi, mm_bahan, mm_gram)
                if hasil is None:
                    st.error(f"Bahan '{mm_bahan}' tidak ditemukan di TKPI.")
                else:
                    st.session_state.mm_draft.append(hasil)
                    st.rerun()

        if st.session_state.mm_draft:
            draft = st.session_state.mm_draft
            df_draft = pd.DataFrame([
                {"Bahan": d["bahan"], "BB (g)": d["bb"],
                 **{g: round(d["zat"][g], 2) for g in pr.NAMA_GIZI}}
                for d in draft
            ])
            st.dataframe(df_draft, width="stretch", height=180, hide_index=True)
            tot_draft = pd.DataFrame([d["zat"] for d in draft]).sum(numeric_only=True)
            st.markdown(
                f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0">'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">⚡ {fmt(tot_draft["Energi"], 0)} kkal</span>'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">🥩 {fmt(tot_draft["Protein"], 1)} g protein</span>'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">🫒 {fmt(tot_draft["Lemak"], 1)} g lemak</span>'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">🌾 {fmt(tot_draft["KH"], 1)} g KH</span></div>',
                unsafe_allow_html=True,
            )
            for i, d in enumerate(draft):
                if st.button(f"🗑️ Keluarkan: {d['bahan']}", key=f"mm_del_{i}"):
                    st.session_state.mm_draft.pop(i)
                    st.rerun()

            df_lib_sekarang = ms.baca_menu(MENU_FILE)
            nama_ada = set(ms.daftar_nama_menu(df_lib_sekarang))
            if st.button("💾 Simpan menu ke Master Menu", type="primary", key="mm_simpan",
                         width="stretch"):
                nama_m = mm_nama.strip()
                if not nama_m:
                    st.error("❌ Nama menu wajib diisi.")
                elif nama_m.lower() in {n.lower() for n in nama_ada}:
                    st.error(f"❌ Menu '{nama_m}' sudah ada di Master Menu.")
                else:
                    rows = [{"bahan": d["bahan"], "bb": d["bb"], "zat": d["zat"]}
                            for d in draft]
                    ms.simpan_menu(MENU_FILE, nama_m, "", rows)
                    st.session_state.mm_log.append(nama_m)
                    st.session_state.mm_draft = []
                    st.success(f"✅ Menu '{nama_m}' tersimpan.")
                    st.rerun()
        else:
            st.markdown('<div style="background:#fff;border:1px solid #E3ECF6;'
                        'border-radius:12px;padding:10px 14px;font-size:13px;color:#5F7A93">'
                        'Cari bahan → pilih → isi gram → klik <b>➕ Masukkan</b>. '
                        'Tambahkan beberapa bahan sampai menu lengkap.</div>',
                        unsafe_allow_html=True)

    with kol_kanan:
        seksi("Master Menu tersimpan")
        df_lib = ms.baca_menu(MENU_FILE)
        nama_lib = ms.daftar_nama_menu(df_lib)
        if not nama_lib:
            st.markdown('<div style="background:#fff;border:1px solid #E3ECF6;'
                        'border-radius:12px;padding:10px 14px;font-size:13px;color:#5F7A93">'
                        'Belum ada menu tersimpan. Buat menu di kolom kiri.</div>',
                        unsafe_allow_html=True)
        else:
            pilih_lib = st.selectbox("Lihat menu", nama_lib, key="mm_pilih_lib")
            baris_menu = df_lib[df_lib["Menu"] == pilih_lib]
            tot_menu = baris_menu[pr.NAMA_GIZI].sum(numeric_only=True)
            st.markdown(
                f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 8px">'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">⚡ {fmt(tot_menu["Energi"], 0)} kkal</span>'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">🥩 {fmt(tot_menu["Protein"], 1)} g</span>'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">🫒 {fmt(tot_menu["Lemak"], 1)} g</span>'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">🌾 {fmt(tot_menu["KH"], 1)} g</span>'
                f'<span style="background:#EAF1FB;border-radius:20px;padding:3px 12px;'
                f'font-size:12px;color:#0A2E6E">🍽 {len(baris_menu)} bahan</span></div>',
                unsafe_allow_html=True,
            )
            df_lihat = baris_menu[["Urutan", "Bahan", "BB"] + pr.NAMA_GIZI].copy()
            for g in pr.NAMA_GIZI:
                df_lihat[g] = df_lihat[g].round(2)
            st.dataframe(df_lihat, width="stretch", height=210, hide_index=True)

            cek_hapus = st.checkbox("Saya yakin ingin menghapus menu ini", key="mm_cek_hapus")
            if st.button(f"🗑️ Hapus menu '{pilih_lib}'", key="mm_hapus",
                         disabled=not cek_hapus, width="stretch"):
                n = ms.hapus_menu(MENU_FILE, pilih_lib)
                if n:
                    st.success(f"✅ Menu '{pilih_lib}' dihapus ({n} bahan).")
                    st.rerun()

    if st.session_state.mm_log:
        seksi("Tersimpan sesi ini")
        st.markdown(" &nbsp; ".join(
            f'<span style="background:#EAF1FB;border:1px solid #C9DCF2;border-radius:20px;'
            f'padding:3px 12px;font-size:12px;color:#0A2E6E">✅ {n}</span>'
            for n in st.session_state.mm_log[-10:]
        ), unsafe_allow_html=True)

# ============ TAB 4: TABEL LENGKAP ============
with tab_tabel:
    st.caption(f"Menampilkan {len(hasil):,} bahan hasil pencarian")
    df_t = hasil.copy()
    for g in pr.NAMA_GIZI:
        df_t[g] = df_t[g].round(2)
    st.dataframe(df_t, width="stretch", height=540)
    b1, b2 = st.columns(2)
    with b1:
        bufe = io.BytesIO()
        with pd.ExcelWriter(bufe, engine="openpyxl") as penulis:
            df_t.to_excel(penulis, index=False, sheet_name="TKPI")
        st.download_button("📥 Download hasil → Excel",
                           data=bufe.getvalue(), file_name="master_tkpi_hasil.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with b2:
        st.download_button("📥 Download hasil → CSV",
                           data=df_t.to_csv(index=False).encode("utf-8-sig"),
                           file_name="master_tkpi_hasil.csv", mime="text/csv")

# ============ TAB 3: BANDINGKAN ============
with tab_banding:
    st.markdown("Pilih 2–4 bahan untuk dibandingkan kandungannya (per 100 g).")
    daftar_b = list(hasil["Nama Bahan Makanan"])
    if len(daftar_b) > 500:
        daftar_b = daftar_b[:500]
    pilihan_b = st.multiselect("Bahan pembanding", daftar_b, key="banding_pilih",
                               max_selections=4)
    if len(pilihan_b) >= 2:
        import plotly.express as px
        sub = hasil[hasil["Nama Bahan Makanan"].isin(pilihan_b)]
        makro = ["Energi", "Protein", "Lemak", "KH"]
        df_long = sub.melt(id_vars="Nama Bahan Makanan", value_vars=makro,
                           var_name="Zat Gizi", value_name="Nilai per 100 g")
        fig = px.bar(df_long, x="Nama Bahan Makanan", y="Nilai per 100 g", color="Zat Gizi",
                     barmode="group", text="Nilai per 100 g",
                     color_discrete_sequence=[BIRU_TUA, BIRU, BIRU_MUDA, "#90CAF9"])
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        st.plotly_chart(gaya_fig(fig), width="stretch")

        seksi("Tabel perbandingan lengkap (per 100 g)")
        tabel_b = sub.set_index("Nama Bahan Makanan").T
        tabel_b = tabel_b.round(2)
        st.dataframe(tabel_b, width="stretch")
    else:
        st.markdown('<div style="background:#fff;border:1px solid #E3ECF6;border-radius:12px;'
                    'padding:12px 14px;font-size:13px;color:#5F7A93">Pilih minimal 2 bahan '
                    'dari daftar di atas untuk melihat perbandingan.</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-app">Master TKPI · data diproses lokal · '
            'dibuat untuk Subdep Gizi · © 2026</div>', unsafe_allow_html=True)
