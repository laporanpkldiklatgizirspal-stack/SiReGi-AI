# Recall Gizi + Master TKPI + Nutri Level — Paket Deploy Web

Aplikasi Recall Gizi (input recall 24 jam ala NutriSurvey + AI ketik makanan +
Buku Foto Porsi), Master TKPI (database bahan makanan, dilindungi login), dan
Nutri Level (scan label Informasi Nilai Gizi → level 🟢🟡🔴 gula/natrium/lemak).

## Isi folder

```
recall-gizi-web/
├── recall/    -> Aplikasi RECALL GIZI (publik, tanpa login)
│   ├── app.py
│   ├── utils/            (mesin hitung, AI, buku foto)
│   ├── data/             (file master TKPI + katalog porsi)
│   ├── assets/buku_foto/ (foto porsi makanan)
│   └── requirements.txt
├── master/    -> Aplikasi MASTER TKPI (wajib login username & password)
│   ├── app_master.py
│   ├── utils/
│   ├── data/
│   └── requirements.txt
├── nutri-level/ -> Aplikasi NUTRI LEVEL (scan label gizi -> level 🟢🟡🔴)
│   ├── app.py
│   ├── nutri_core.py
│   ├── assets/logo_rspal.png
│   └── requirements.txt
├── .gitignore
└── README.md
```

## Cara deploy (Streamlit Community Cloud — gratis)

1. Buat akun di https://github.com lalu buat **repository baru** (nama bebas,
   mis. `recall-gizi-web`). Biarkan **Public** (gratis).
2. Upload isi folder `recall-gizi-web` ini ke repo (bisa lewat web GitHub:
   *Add file → Upload files*, atau pakai GitHub Desktop).
3. Buka https://share.streamlit.io → **Sign in with GitHub** → **New app** →
   pilih repo-nya → tentukan **Main file path**:
   - Aplikasi Recall (link publik)   : `recall/app.py`
   - Aplikasi Master (link terkunci) : `master/app_master.py`
   Lakukan deploy 2x (satu untuk tiap main file path) — hasilnya 2 link
   `<nama>.streamlit.app`.
4. Untuk aplikasi MASTER: buka app-nya di dashboard → **Settings →
   Secrets** → isi:
   ```toml
   [master]
   username = "admin"
   password = "ganti123"
   ```
   (ganti username/password sesuai keinginan — file `.streamlit/secrets.toml`
   lokal TIDAK ikut ter-upload, itu sengaja.)
5. Selesai — setiap kali mau perbarui fitur: edit di laptop → upload ulang
   file yang berubah ke GitHub → website otomatis ter-deploy ulang.

## Catatan penting

- Data diolah oleh aplikasi; file master yang di-upload pengunjung hanya
  berlaku untuk sesi itu (tidak mengubah file di repo).
- Perubahan permanen pada database master dilakukan dari laptop, lalu
  file `data/MASTER_TKPI__Recall.xlsx` di-upload ulang ke repo.
- Custom domain (mis. `gizi-rspal.id`): deploy dulu seperti di atas; nanti
  domain bisa dibeli & diarahkan (Railway/Render/redirect) tanpa mengubah kode.
