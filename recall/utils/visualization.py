"""Visualisasi dengan Plotly: grafik yang rapi dan konsisten."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

WARNA = ["#0e7c66", "#1565c0", "#e9a13b", "#c62828", "#7b5ea7", "#2a9d8f"]

TEMPLATE = "plotly_white"


def _gaya(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template=TEMPLATE,
        margin=dict(l=20, r=20, t=45, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(family="Segoe UI, Arial", size=13),
        colorway=WARNA,
    )
    return fig


def grafik_tren(df: pd.DataFrame, judul: str = "Tren Bulanan") -> go.Figure:
    """Line chart tren. df berisi kolom 'Bulan' dan kolom nilai kedua."""
    if df.empty or df.shape[1] < 2:
        return go.Figure()
    kol_nilai = df.columns[1]
    fig = px.line(df, x="Bulan", y=kol_nilai, markers=True, title=judul)
    fig.update_traces(line=dict(width=3, color="#0e7c66"))
    return _gaya(fig)


def grafik_bar(df: pd.DataFrame, judul: str = "Perbandingan Kategori") -> go.Figure:
    """Bar chart. df berisi kolom kategori (kolom 1) dan nilai (kolom 2)."""
    if df.empty or df.shape[1] < 2:
        return go.Figure()
    kol_kat = df.columns[0]
    kol_nilai = df.columns[1]
    fig = px.bar(
        df,
        x=kol_kat,
        y=kol_nilai,
        title=judul,
        text=kol_nilai,
        color=kol_kat,
        color_discrete_sequence=WARNA,
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(showlegend=False, xaxis_tickangle=-30)
    return _gaya(fig)


def grafik_pie(df: pd.DataFrame, judul: str = "Proporsi") -> go.Figure:
    """Pie/donut. df berisi kolom kategori (kolom 1) dan nilai (kolom 2)."""
    if df.empty or df.shape[1] < 2:
        return go.Figure()
    kol_kat = df.columns[0]
    kol_nilai = df.columns[1]
    fig = px.pie(df, names=kol_kat, values=kol_nilai, hole=0.45, title=judul)
    fig.update_traces(textinfo="percent+label")
    return _gaya(fig)
