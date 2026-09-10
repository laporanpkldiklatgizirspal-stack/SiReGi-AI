"""
GiziLens — komponen tampilan HTML (kartu, progress bar, banner, hero).
Streamlit murni (tanpa logika database/kalkulator).
"""

from __future__ import annotations

import base64
from pathlib import Path

import config
from utils import fmt_jumlah, fmt_persen

_WARNA = config.COLORS
_BG_SOFT = {
    "safe": "#E8F9EF",
    "warning": "#FEF3E2",
    "danger": "#FDECEC",
}

# Palet biru RSPAL
BIRU_TUA = "#0A2E6E"
BIRU = "#1565C0"
ABU = "#5F7A93"
TEKS = "#10233F"

_LOGO = Path(__file__).resolve().parent / "assets" / "logo_rspal.png"


def css() -> str:
    return f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif; }}
  .stApp, [data-testid="stAppViewContainer"] {{
    background:
      radial-gradient(1100px 460px at 88% -8%, #EAF1FB 0%, rgba(234,241,251,0) 60%),
      linear-gradient(180deg, #F7FAFD 0%, #F1F6FC 100%) !important;
  }}
  [data-testid="stHeader"] {{ background: transparent; }}
  h1, h2, h3 {{ color: {BIRU_TUA}; }}
  .hero {{
    position: relative; overflow: hidden;
    background: linear-gradient(120deg, {BIRU_TUA} 0%, {BIRU} 58%, #2E86DE 100%);
    border-radius: 24px; padding: 24px 28px 20px; margin: 6px 0 14px;
    box-shadow: 0 10px 30px rgba(10,46,110,.22); color:#fff; text-align:center;
  }}
  .hero-logo {{ height: 58px; filter: drop-shadow(0 2px 4px rgba(0,0,0,.15)); }}
  .hero h1 {{ color:#fff; font-size:32px; font-weight:800; margin:2px 0; }}
  .hero .org {{ color:#D8E6FB; font-size:12.5px; font-weight:600; }}
  .hero .tag {{ color:#EAF2FF; font-size:14px; margin-top:4px; }}
  .judul-seksi {{ font-size:20px; font-weight:800; color:{BIRU_TUA}; margin:16px 0 2px; }}
  .sub-seksi {{ color:{ABU}; font-size:13.5px; margin-bottom:8px; }}
  .panel {{ background:#fff; border:1px solid #E2EDF8; border-radius:16px;
            padding:14px 16px; margin:8px 0; box-shadow:0 3px 12px rgba(10,46,110,.05); }}
  .kartu-info {{ background:#EAF1FB; border-left:4px solid {BIRU}; border-radius:10px;
                 padding:10px 14px; font-size:14px; color:{TEKS}; margin:8px 0; }}
  .kartu-warning {{ background:#FFF7E6; border:1px solid #F5D68C; border-left:5px solid {_WARNA['warning']};
                   border-radius:10px; padding:10px 14px; font-size:14px; color:#7A4E03; margin:8px 0; }}
  .banner-danger {{ background:linear-gradient(120deg,#7F1D1D,#DC2626); color:#fff; border-radius:16px;
                    padding:14px 18px; margin:10px 0; box-shadow:0 8px 22px rgba(220,38,38,.2); }}
  .banner-danger b {{ font-size:16px; }}
  .banner-danger p {{ margin:5px 0 0; font-size:14px; line-height:1.5; }}
  .kartu-ggl {{ border:1px solid #E2EDF8; border-top:5px solid {BIRU}; border-radius:16px;
               background:#fff; padding:14px 12px; text-align:center; height:100%;
               box-shadow:0 3px 12px rgba(10,46,110,.06); }}
  .kartu-ggl .head {{ font-size:12.5px; font-weight:800; color:{TEKS}; letter-spacing:.6px; }}
  .kartu-ggl .nilai {{ font-size:26px; font-weight:800; color:{TEKS}; line-height:1.1; margin-top:2px; }}
  .kartu-ggl .nilai .unit {{ font-size:14px; font-weight:700; color:{ABU}; }}
  .kartu-ggl .pct {{ font-size:13px; color:{ABU}; font-weight:600; margin:2px 0 6px; }}
  .bar {{ height:8px; border-radius:99px; background:#EEF3F9; overflow:hidden; margin:0 2px 8px; }}
  .bar i {{ display:block; height:100%; border-radius:99px; }}
  .pill {{ display:inline-block; border-radius:999px; padding:4px 12px; font-size:12px;
           font-weight:800; }}
  .footer-app {{ text-align:center; color:{ABU}; font-size:11.5px; margin-top:24px; }}
  [data-testid="stCameraInput"] {{
    border:1px solid #D8E6F5 !important; border-radius:18px !important;
    overflow:hidden; box-shadow:0 4px 14px rgba(10,46,110,.08);
  }}
  [data-testid="stCameraInput"] video {{ object-fit:cover; }}
</style>"""


def hero(judul: str = config.APP_NAME, tagline: str = config.APP_TAGLINE):
    import streamlit as st
    b64 = ""
    if _LOGO.exists():
        b64 = base64.b64encode(_LOGO.read_bytes()).decode()
    logo = (f'<img class="hero-logo" src="data:image/png;base64,{b64}" alt="logo"/>'
            if b64 else "")
    st.markdown(
        f'<div class="hero">{logo}<h1>{judul}</h1>'
        f'<div class="org">{config.ORG}</div>'
        f'<div class="tag">{tagline}</div></div>',
        unsafe_allow_html=True,
    )


def judul_seksi(teks: str, sub: str = ""):
    import streamlit as st
    st.markdown(f'<div class="judul-seksi">{teks}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="sub-seksi">{sub}</div>', unsafe_allow_html=True)


def pill(warna: str, teks: str) -> str:
    return (f'<span class="pill" style="color:{_WARNA.get(warna, "#333")};'
            f'background:{_BG_SOFT.get(warna, "#eee")};">{teks}</span>')


def bar(persen: float, warna: str) -> str:
    lebar = max(2.0, min(100.0, persen))
    return (f'<div class="bar"><i style="width:{lebar:.1f}%;'
            f'background:{_WARNA.get(warna, "#888")};"></i></div>')


def kartu_total(emoji: str, label: str, konsumsi: float, batas: float,
                unit: str, ringkasan: dict, baris_tambahan: list[str] | None = None,
                sub_batas: str | None = None) -> str:
    """Satu kartu besar GGL (spec: nilai/batas, %, sisa, badge warna)."""
    warna = ringkasan["warna"]
    badge_teks, _pesan = ringkasan["badge"], ringkasan["pesan"]
    sisa = ringkasan["sisa"]
    tambahan = "".join(f'<div class="pct">{t}</div>' for t in (baris_tambahan or []))
    sub = f'<div class="pct">batas: {fmt_jumlah(batas)} {unit}{" " + sub_batas if sub_batas else ""}</div>' \
        if sub_batas else ""
    if ringkasan["lebih"] > 0:
        sisa_teks = (f'<div class="pct" style="color:{_WARNA["danger"]};font-weight:700;">'
                     f'🔴 +{fmt_jumlah(ringkasan["lebih"])} {unit} di atas batas harian</div>')
    else:
        sisa_teks = f'<div class="pct">Sisa: {fmt_jumlah(sisa)} {unit}</div>'
    return f"""
    <div class="kartu-ggl" style="border-top-color:{_WARNA[warna]};">
      <div class="head">{emoji} {label}</div>
      <div class="nilai">{fmt_jumlah(konsumsi)}<span class="unit"> / {fmt_jumlah(batas)} {unit}</span></div>
      {sub}{tambahan}
      <div class="pct" style="font-weight:700;">{fmt_persen(ringkasan['persen'])}%</div>
      {bar(ringkasan['persen'], warna)}
      {sisa_teks}
      {pill(warna, badge_teks)}
    </div>"""


_NL_WARNA = config.NUTRI_LEVEL_WARNA


def kartu_nutri_level(hasil_nl: dict, nama_jenis: str = "minuman") -> str:
    """Kartu besar Nutri-Level: huruf A–D + rincian huruf tiap zat gizi."""
    if not hasil_nl:
        return ""
    level = hasil_nl.get("level") or "A"
    warna = _NL_WARNA.get(level, "#888")
    sebutan = config.NUTRI_LEVEL_KETERANGAN.get(level, "")
    satuan = hasil_nl.get("satuan", "per 100 mL")

    baris = []
    for zat, huruf in (hasil_nl.get("level_zat") or {}).items():
        nama = {"gula": "🍬 Gula", "natrium": "🧂 Garam (natrium)", "lemak_jenuh": "🥑 Lemak jenuh"}.get(zat, zat)
        nilai = (hasil_nl.get("per100") or {}).get(zat)
        sat = "g" if zat != "natrium" else "mg"
        if huruf:
            w = _NL_WARNA.get(huruf, "#888")
            baris.append(
                f'<div class="nl-baris"><span>{nama}</span>'
                f'<span class="nl-nilai">{fmt_jumlah(nilai)} {sat}</span>'
                f'<span class="nl-huruf" style="color:#fff;background:{w}">{huruf}</span></div>'
            )
        else:
            baris.append(
                f'<div class="nl-baris"><span>{nama}</span>'
                f'<span class="nl-nilai">belum ada angkanya</span>'
                f'<span class="nl-huruf" style="color:#5F7A93;background:#EEF3F9">–</span></div>'
            )

    # strip resmi A · B · C · D (kotak aktif = level produk)
    kotak = []
    for huruf in ("A", "B", "C", "D"):
        aktif = (huruf == level)
        kotak.append(
            f'<span class="nl-slot{" aktif" if aktif else ""}" '
            f'style="background:{_NL_WARNA[huruf]};{"opacity:.35;" if not aktif else ""}">{huruf}</span>'
        )
    strip = ('<div class="nl-strip">' + "".join(kotak) + "</div>"
             '<div class="nl-strip-ket">GGL paling rendah ← → GGL paling tinggi</div>')

    catatan = ""
    if not hasil_nl.get("tersedia"):
        catatan = ('<div class="kartu-warning" style="margin-top:10px">📋 Ambang Nutri-Level untuk '
                   '<b>makanan (per 100 g)</b> belum diisi di aplikasi. Isi angkanya di menu '
                   '<b>⚙️ Pengaturan</b> sesuai poster/aturan resmi — setelah itu huruf Nutri-Level '
                   'produk makanan akan dihitung otomatis.</div>')
    elif not hasil_nl.get("lengkap"):
        kurang = ", ".join({"gula": "gula", "natrium": "garam", "lemak_jenuh": "lemak jenuh"}.get(z, z)
                           for z in hasil_nl.get("zat_kurang", []))
        catatan = (f'<div class="kartu-warning" style="margin-top:10px">ℹ️ Angka <b>{kurang}</b> belum ada, '
                   'jadi huruf Nutri-Level di atas baru dari zat yang ada angkanya. Lengkapi angkanya '
                   'untuk hasil yang pasti.</div>')

    return f"""
    <div class="kartu-nl" style="border-top-color:{warna};">
      <div class="nl-head">🏷️ NUTRI-LEVEL (KEMENKES)</div>
      {strip}
      <div class="nl-badge" style="background:{warna};">{level}</div>
      <div class="nl-sebutan">{sebutan}</div>
      <div class="nl-jenis">{'Minuman' if nama_jenis == 'minuman' else 'Makanan'} · dinilai {satuan}</div>
      {''.join(baris)}
      {catatan}
      <div class="nl-sumber">Dasar: {config.NUTRI_LEVEL_SUMBER}. Ambang batas diambil dari poster resmi;
      penilaian memakai kandungan per 100 {'mL' if nama_jenis == 'minuman' else 'g'}.</div>
    </div>"""


def css_nutri_level() -> str:
    return """
<style>
  .kartu-nl {{ background:#fff; border:1px solid #E2EDF8; border-top:6px solid #1565C0; border-radius:18px;
              padding:16px 16px 14px; margin:10px 0; box-shadow:0 4px 14px rgba(10,46,110,.07); text-align:center; }}
  .kartu-nl .nl-head {{ font-size:12.5px; font-weight:800; letter-spacing:.8px; color:#10233F; }}
  .kartu-nl .nl-strip {{ display:flex; gap:8px; justify-content:center; margin:10px 0 2px; }}
  .kartu-nl .nl-slot {{ width:38px; height:38px; border-radius:11px; color:#fff; font-size:19px;
                       font-weight:800; line-height:38px; }}
  .kartu-nl .nl-slot.aktif {{ transform:scale(1.18); box-shadow:0 0 0 3px #fff, 0 0 0 6px rgba(10,46,110,.25); }}
  .kartu-nl .nl-strip-ket {{ font-size:10.5px; color:#8AA0B8; margin-bottom:6px; }}
  .kartu-nl .nl-badge {{ width:96px; height:96px; margin:10px auto 6px; border-radius:26px; color:#fff;
                        font-size:56px; font-weight:800; line-height:96px; }}
  .kartu-nl .nl-sebutan {{ font-size:14px; font-weight:800; color:#0A2E6E; }}
  .kartu-nl .nl-jenis {{ font-size:11.5px; color:#5F7A93; margin-bottom:10px; }}
  .kartu-nl .nl-baris {{ display:flex; align-items:center; gap:8px; justify-content:space-between;
                        border-top:1px dashed #E2EDF8; padding:8px 2px; font-size:13.5px; }}
  .kartu-nl .nl-nilai {{ color:#5F7A93; font-weight:700; margin-left:auto; }}
  .kartu-nl .nl-huruf {{ min-width:28px; height:28px; border-radius:9px; font-weight:800; font-size:14px;
                        line-height:28px; text-align:center; }}
  .kartu-nl .nl-sumber {{ font-size:10.5px; color:#8AA0B8; margin-top:10px; text-align:left; line-height:1.5; }}
</style>"""


def banner_peringatan(judul: str, isi: str):
    import streamlit as st
    st.markdown(f'<div class="banner-danger"><b>{judul}</b><p>{isi}</p></div>',
                unsafe_allow_html=True)


def info_box(html_isi: str):
    import streamlit as st
    st.markdown(f'<div class="kartu-info">{html_isi}</div>', unsafe_allow_html=True)


def footer():
    import streamlit as st
    st.markdown(
        f'<div class="footer-app">GiziLens · alat edukasi & pencatatan konsumsi GGL · '
        f'dibuat oleh {config.ORG_SINGKAT} · © 2026</div>',
        unsafe_allow_html=True,
    )
