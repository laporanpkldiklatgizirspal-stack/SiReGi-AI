# -*- coding: utf-8 -*-
"""Gerbang login username & password untuk aplikasi (mis. Master TKPI).

Kredensial dibaca dari st.secrets -> bagian [master]:
  - Lokal : file .streamlit/secrets.toml  (jangan di-upload ke GitHub)
  - Cloud : Streamlit Community Cloud -> Settings -> Secrets

Contoh isi .streamlit/secrets.toml:
    [master]
    username = "admin"
    password = "ganti123"

Setelah login berhasil, sesi ditandai auth_master = True (berlaku sampai
browser ditutup / tombol Keluar ditekan).
"""
from __future__ import annotations

import streamlit as st


def ambil_kredensial() -> tuple[str, str]:
    """(username, password) dari st.secrets; kosong bila belum dikonfigurasi."""
    try:
        return (
            str(st.secrets["master"]["username"]),
            str(st.secrets["master"]["password"]),
        )
    except Exception:  # noqa: BLE001
        return "", ""


def sudah_masuk() -> bool:
    return bool(st.session_state.get("auth_master", False))


def tombol_keluar(sidebar: bool = True) -> None:
    """Tombol 'Keluar' — tempatkan di sidebar setelah login."""
    if sidebar:
        with st.sidebar:
            if st.button("🚪 Keluar", use_container_width=True):
                st.session_state["auth_master"] = False
                st.rerun()
    else:
        if st.button("🚪 Keluar"):
            st.session_state["auth_master"] = False
            st.rerun()


def tampilkan_login(judul: str = "🔒 Halaman Terkunci",
                    sub: str = "Masukkan username & password untuk membuka "
                               "aplikasi ini.") -> bool:
    """Tampilkan formulir login. True bila sudah/login berhasil."""
    if sudah_masuk():
        return True
    u, p = ambil_kredensial()
    if not u:
        st.error("⚠️ Login belum dikonfigurasi. Admin: buat file "
                 "`.streamlit/secrets.toml` (lokal) atau set **Secrets** "
                 "di pengaturan aplikasi (cloud) dengan bagian [master] "
                 "berisi username & password.")
        return False

    st.markdown(
        f"""
        <div style="max-width:420px;margin:40px auto 10px;text-align:center">
          <div style="font-size:44px">🔐</div>
          <div style="font-size:22px;font-weight:800;color:#0A2E6E;margin-top:4px">
            {judul}</div>
          <div style="font-size:13px;color:#5F7A93;margin-top:2px">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("form_login"):
        nu = st.text_input("Username", placeholder="username")
        np_ = st.text_input("Password", type="password", placeholder="••••••••")
        masuk = st.form_submit_button("🔓 Masuk", type="primary",
                                      use_container_width=True)
    if masuk:
        if nu.strip() == u and np_ == p:
            st.session_state["auth_master"] = True
            st.rerun()
        else:
            st.error("❌ Username atau password salah. Coba lagi.")
    st.markdown(
        '<div style="max-width:420px;margin:6px auto;text-align:center;'
        'font-size:11.5px;color:#9DB1C7">Hubungi admin bila lupa '
        'password.</div>',
        unsafe_allow_html=True,
    )
    return False
