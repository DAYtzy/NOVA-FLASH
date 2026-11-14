# NOVA FLASH

Aplikasi berbagi foto/video ala Instagram: feed, posting foto/video, like, komentar, follow, dan profil.
Satu keluarga dengan NOVA WAWA — frontend HTML/CSS/JS biasa, backend Flask, database PostgreSQL (Neon), di-host di Vercel.

## Struktur
| File | Isi |
|---|---|
| `app.py` | Semua rute API (Flask) |
| `database.py` | Tabel database (SQLAlchemy): User, Post, Like, Comment, Follow |
| `security.py` | Header keamanan (CSP), aturan password, validasi gambar/video |
| `index.html` | Satu halaman untuk layar masuk/daftar dan aplikasi (feed, profil) |
| `script.js` `style.css` | Logika dan tampilan |
| `sw.js` `manifest.json` `icon-*.png` | PWA (bisa "dipasang" di HP) |
| `vercel.json` | Konfigurasi Vercel (server di Singapura) |

## Variabel lingkungan (Vercel: Settings → Environment Variables)
| Nama | Wajib? | Fungsi |
|---|---|---|
| `SECRET_KEY` | **Ya** (min. 16 karakter) | Menandatangani token login. Tanpa ini API menolak jalan |
| `DATABASE_URL` | **Ya** | Alamat database Neon |

## Menjalankan di komputer
```
pip install -r requirements.txt
python app.py
```
Tanpa `DATABASE_URL`, aplikasi memakai SQLite lokal (`nova.db`), jalan di `http://localhost:5001`.

## Versi ini (v1) — yang sudah ada
- Daftar & masuk (email/username + password), token 30 hari
- Posting foto/video (disimpan sebagai data-URL di database, maksimal ~6MB per file)
- Feed terbaru dari semua pengguna, like, dan komentar
- Follow/unfollow, halaman profil dengan grid post, edit bio

## Yang belum ada (lanjutan dari NOVA WAWA, bisa ditambah menyusul)
- Penyimpanan media di Cloudinary (supaya tidak terbatas ~6MB dan tidak membebani database)
- Story 24 jam, explore/pencarian, notifikasi, pesan langsung (DM)
- Verifikasi email, lupa password, panel owner — bisa disalin polanya dari NOVA WAWA (`mailer.py`, `push.py`)

## Batasan yang perlu diketahui
- Media disimpan langsung di database (data-URL) pada v1 ini — cocok untuk coba-coba/MVP, tapi akan cepat
  memenuhi kuota database kalau dipakai banyak orang. Pasang Cloudinary secepatnya kalau mau produksi.
- Feed belum dipersonalisasi (belum berbasis following) — masih menampilkan semua post terbaru.
