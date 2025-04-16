# Musik Web App 🎵

Aplikasi web musik berbasis **Flask** Python yang memungkinkan pengguna untuk mencari lagu, mengunduh lagu dari YouTube dan Spotify, membuat playlist, serta memutar lagu langsung di browser. Aplikasi ini dikembangkan oleh **Sakum** dan dibantu oleh AI untuk mempercepat pengembangan serta otomasi berbagai fitur canggih.

---

## ✨ Fitur
- 🔍 **Pencarian Lagu**: Fungsi pencarian lagu yang muncul sesuai judul music yang ada di database anda.
- ⬇️ **Unduh Lagu**: Lagu akan diunduh otomatis.
- 📁 **Playlist**: Masih Blum berfungsi masih pengembangan.
- 🎧 **Pemutar Musik**: Putar lagu langsung di dalam browser dengan tampilan sederhana dan responsif.
- 🛠️ **Admin Panel**: Admin dapat mengunggah lagu dengan otomatis hanya dengan menempelkan link music dari youtube maupun spotify dan juga ada untuk mengedit lagu atau menghapus lagu.
- ⚙️ **Minifikasi Otomatis**: HTML, CSS, dan JavaScript akan di-minify otomatis agar lebih cepat saat diakses.
- 🔐 **Login dan Register**: Fitur otentikasi pengguna masih belum sempurna.

---

## ⚙️ Teknologi yang Digunakan
- **Backend**: Python + Flask
- **Database**: MySQL (pymysql)
- **YouTube API**: Untuk metadata dan pencarian lagu
- **Spotify API**: Untuk metadata lagu
- **YT-DLP**: Downloader lagu dari YouTube
- **Flask-Minify**: Untuk minifikasi otomatis HTML, JS, CSS
- **python-dotenv**: Memuat konfigurasi sensitif dari file `.env`

---

## 🧩 Struktur Tabel Untuk Menyimpan Music

| No | Kolom              | Tipe Data      | Nullable | Default Value       | Keterangan                                   |
|----|--------------------|----------------|----------|---------------------|----------------------------------------------|
| 1  | `id`               | `int(11)`      | Tidak    | `AUTO_INCREMENT`     | ID utama, unik untuk setiap lagu             |
| 2  | `judul`            | `varchar(255)`  | Tidak    | Tidak ada            | Judul lagu                                   |
| 3  | `artis`            | `varchar(255)`  | Ya       | `NULL`               | Nama artis atau penyanyi                     |
| 4  | `deskripsi`        | `text`          | Ya       | `NULL`               | Deskripsi lagu                               |
| 5  | `nama_file_audio`  | `varchar(255)`  | Tidak    | Tidak ada            | Nama file audio yang diunduh                 |
| 6  | `thumbnail`        | `varchar(255)`  | Ya       | `NULL`               | URL atau path thumbnail lagu                 |
| 7  | `tanggal_upload`   | `datetime`      | Ya       | `current_timestamp()` | Waktu pengunggahan lagu                      |
| 8  | `is_public`        | `tinyint(1)`    | Ya       | `1`                  | Status publikasi lagu                        |
| 9  | `visibility`       | `varchar(10)`   | Ya       | `public`             | Visibilitas (public/private)                 |
| 10 | `duration`         | `int(11)`       | Ya       | `0`                  | Durasi lagu dalam detik                      |
| 11 | `plays`            | `int(11)`       | Ya       | `0`                  | Jumlah pemutaran lagu                        |
| 12 | `likes`            | `int(11)`       | Ya       | `0`                  | Jumlah suka                                  |
| 13 | `playlist_id`      | `int(11)`       | Ya       | `NULL`               | ID playlist terkait                          |
| 14 | `random_id`        | `varchar(16)`   | Ya       | `NULL`               | ID acak lagu                                 |

---

## 🚀 Instalasi

1. **Clone Repository**
   ```bash
   git clone https://github.com/SakumDisiniPa/web-music.git
   cd web-music
   ```

2. **Buat dan aktifkan virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # di Linux/macOS
   source venv/bin/activate.fish  # jika menggunakan terminal fish
   venv\Scripts\activate   # di Windows
   ```

3. **Instal semua dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Buat file `.env`**
   ```env
   DB_HOST=localhost #sesuai host 
   DB_USER=root #sesuaikan user 
   DB_PASSWORD=#password kamu jika tidak ada kosongkan saja
   DB_NAME=#nama database kamu
    
    SPOTIFY_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
    SPOTIFY_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxx
    YOUTUBE_API_KEY=xxxxxxxxxxxxxxxxxxxx
   ```

5. **Jalankan aplikasinya**
   ```bash
   python server.py
   python3 server.py #jika pertama gagal
   ```

---

## 📸 Screenshot (Opsional)
Kamu bisa menambahkan screenshot dari tampilan utama, halaman pemutar musik, atau halaman admin.

---

## 🔐 Cara Mendapatkan API Key

Aplikasi ini membutuhkan API Key untuk mengakses layanan YouTube dan Spotify. Berikut langkah-langkah untuk mendapatkannya:

### 🎬 YouTube Data API v3

Untuk menggunakan pencarian lagu dan metadata dari YouTube:

1. Kunjungi [Google Cloud Console](https://console.cloud.google.com/).
2. Buat atau pilih proyek yang ingin kamu gunakan.
3. Buka menu **API & Services > Library**.
4. Cari **YouTube Data API v3**, lalu klik **Enable**.
5. Buka **API & Services > Credentials**.
6. Klik **Create Credentials > API Key**.
7. Salin API Key yang muncul dan tambahkan ke file `.env` kamu:

   ```env
   YOUTUBE_API_KEY=API_KEY_KAMU
   ```

---

### 🎧 Spotify API (Client ID & Secret)

Untuk menggunakan metadata lagu dari Spotify:

1. Kunjungi [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Login dan klik **Create an App**.
3. Setelah dibuat, buka aplikasi dan salin **Client ID** dan **Client Secret**.
4. Tambahkan ke file `.env` kamu seperti berikut:

   ```env
   SPOTIFY_CLIENT_ID=CLIENT_ID_KAMU
   SPOTIFY_CLIENT_SECRET=CLIENT_SECRET_KAMU
   ```

---

## 📄 [Lisensi](https://github.com/SakumDisiniPa/web-music/blob/main/LICENSE)
Open source project by Sakum & AI 🤖. Bebas digunakan untuk belajar dan pengembangan.

---
```
