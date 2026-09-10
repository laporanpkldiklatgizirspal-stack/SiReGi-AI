# GiziLens (versi JavaScript / HTML)

Aplikasi **GiziLens** dalam bentuk **satu berkas HTML** — tanpa server Python, tanpa instalasi.
Cocok dibuka **langsung dari HP** (kamera HP jalan), bisa dipasang ke layar utama, dan bisa **offline**.

Fitur sama dengan versi Python/Streamlit:
📷 scan label Informasi Nilai Gizi (kamera / pilih foto) → 🤖 AI Vision Gemini *atau* OCR Tesseract di HP
→ 🔎 periksa & koreksi angka (gula · natrium · lemak) → 🍽️ pilih jumlah sajian → 📊 dampak ke total harian
→ ➕ simpan → 🟢🟡🔴 dashboard, riwayat, ringkasan 7 hari, edukasi, pengaturan.

## Isi folder
| Berkas | Fungsi |
|---|---|
| `index.html` | seluruh aplikasi (HTML + CSS + JavaScript) |
| `manifest.webmanifest` | agar bisa "Add to Home Screen" seperti aplikasi |
| `sw.js` | service worker — supaya bisa dibuka offline |
| `assets/logo_rspal.png` | logo di halaman Beranda |

## Cara pakai

### 1) Paling mudah — dari laptop (Windows)
Klik-2x **`Jalankan GiziLens Web.bat`** di Desktop → browser terbuka di `http://localhost:8505`.
(Atau klik-2x `index.html`.)

### 2) Paling nyaman — dari HP (butuh alamat https)
1. Buka **https://laporanpkldiklatgizirspal-stack.github.io/SiReGi-AI/gizilens-web/**
   (aktifkan dulu GitHub Pages: repo → **Settings** → **Pages** → Source: *Deploy from a branch* →
   Branch: `master` / folder `/ (root)` → **Save**, tunggu ±2 menit).
2. Di Chrome HP → menu ⋮ → **Add to Home screen** / **Tambahkan ke layar utama**.
3. Ikon GiziLens muncul seperti aplikasi biasa; kamera langsung jalan (https = izin kamera aktif).

> Catatan: kamera browser hanya diizinkan pada alamat **https** (GitHub Pages) atau **localhost**.
> Kalau dibuka dari berkas biasa, tetap bisa pakai tombol **pilih foto** (foto dulu dengan kamera HP).

## Pembaca label (2 pilihan)
- **AI Vision Gemini** (paling akurat, terutama label 2 bahasa) — isi kunci gratis dari
  <https://aistudio.google.com/apikey> di menu **⚙️ Pengaturan**. Kunci hanya disimpan di perangkat.
- **OCR Tesseract** (gratis, jalan di HP) — dipakai otomatis bila kunci AI kosong/gagal.
  Sekali pakai butuh internet untuk mengunduh model (±5 MB), setelah itu tersimpan.
- Kalau keduanya gagal → angka bisa **diisi manual** sesuai label kemasan.

## Penyimpanan data
Catatan konsumsi disimpan di **perangkat sendiri** (`localStorage` browser), bukan di server.
Jadi: **selalu unduh backup** (menu 📅 Riwayat → *Unduh Backup JSON* atau *Unduh CSV*) sebelum
berganti HP / membersihkan data browser.

## Batas harian (dapat diubah di ⚙️ Pengaturan)
| Zat | Batas/hari | Setara |
|---|---|---|
| 🍬 Gula | 50 g | ± 4 sendok makan |
| 🧂 Garam/Natrium | 2.000 mg natrium | ± 1 sendok teh garam (5 g) |
| 🥑 Lemak | 67 g | ± 5 sendok makan |

Sumber: **Permenkes RI No. 30 Tahun 2013** & rekomendasi **WHO**. Ambang warna: 🟢 <50% · 🟡 50–99% · 🔴 ≥100%.

⚠️ GiziLens adalah alat edukasi & pencatatan, bukan alat diagnosis. Selalu periksa hasil pembacaan
AI/OCR dengan label asli produk.

---
Dikembangkan oleh Subdep Gizi RSPAL dr. Ramelan · © 2026
