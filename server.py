from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for, Response, stream_with_context, make_response, render_template, send_file
import os
import pymysql
import subprocess
import urllib.request
import smtplib
import re
import uuid
import shutil
import spotipy
import base64
import time
import logging
import json 
import bcrypt
import yt_dlp
import secrets
import traceback
from spotipy.oauth2 import SpotifyClientCredentials
from googleapiclient.discovery import build
from youtube_search import YoutubeSearch
from werkzeug.utils import secure_filename
from datetime import datetime
from threading import Thread
from functools import lru_cache
from email.mime.text import MIMEText
from yt_dlp import YoutubeDL
from flask_minify import minify
from dotenv import load_dotenv
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth

load_dotenv()

app = Flask(__name__)  # Ini yang hilang!
CORS(app, supports_credentials=True)
app = Flask(__name__, static_folder='public', static_url_path='/public')
# Aktifkan minifikasi untuk HTML, CSS, dan JS
minify(app=app, html=True, js=True, cssless=True)
app.secret_key = secrets.token_hex(16)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,  # Pastikan HTTPS digunakan
)

#API Credentials
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")
oauth = OAuth(app)

# --- GitHub OAuth ---
oauth.register(
    name='github',
    client_id= os.getenv("GITHUB_CLIENT_ID"),
    client_secret= os.getenv("GITHUB_CLIENT_SECRET"),
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

# --- Google OAuth (FIXED: pakai userinfo endpoint) ---
oauth.register(
    name='google',
    client_id= os.getenv("GOOGLE_CLIENT_ID"),
    client_secret= os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# --- Facebook OAuth ---
oauth.register(
    name='facebook',
    client_id= os.getenv("FACEBOOK_CLIENT_ID"),
    client_secret= os.getenv("FACEBOOK_CLIENT_SECRET"),
    access_token_url='https://graph.facebook.com/v17.0/oauth/access_token',
    authorize_url='https://www.facebook.com/v17.0/dialog/oauth',
    api_base_url='https://graph.facebook.com/v17.0/',
    client_kwargs={'scope': 'email'},
)

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfigurasi Database
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),  # Default ke 'localhost' jika tidak ditemukan
    'user': os.getenv('DB_USER'),      # Default ke 'root' jika tidak ditemukan
    'password': os.getenv('DB_PASSWORD'),  # Default ke '' jika tidak ditemukan
    'database': os.getenv('DB_DATABASE'),  # Default ke '' jika tidak ditemukan
    'cursorclass': pymysql.cursors.DictCursor
}

# Inisialisasi Spotify Client dengan error handling
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    ))
except Exception as e:
    logger.error(f"Gagal inisialisasi Spotify client: {e}")
    sp = None

# Fungsi untuk koneksi database
def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

# Cache untuk metadata
@lru_cache(maxsize=100)
def get_youtube_metadata_cached(youtube_url):
    return get_youtube_metadata(youtube_url)

@lru_cache(maxsize=100)
def get_spotify_metadata_cached(spotify_url):
    return get_spotify_metadata(spotify_url)

def extract_youtube_id(url):
    """Ekstrak ID video dari URL YouTube"""
    match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None

# Fungsi untuk menghasilkan ID acak (huruf dan angka)
def generate_random_string(length=8):
    return secrets.token_urlsafe(length)

def encode_path(path):
    return base64.urlsafe_b64encode(path.encode()).decode()

def decode_path(encoded):
    return base64.urlsafe_b64decode(encoded.encode()).decode()

def send_verification_email(to_email, verification_code):
    from_email = "232410226@smkn1padaherang.sch.id"
    from_password = "olxh imsi zszc dlyt"

    msg = MIMEText(f"Klik link ini untuk verifikasi akun kamu: https:sakum.my.id/api/auth/verify?code={verification_code}")
    msg['Subject'] = "Verifikasi Akun"
    msg['From'] = from_email
    msg['To'] = to_email

    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(from_email, from_password)
    server.send_message(msg)
    server.quit()

def extract_video_id(youtube_url):
    """Ekstrak video ID dari URL YouTube"""
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, youtube_url)
    return match.group(1) if match else None

#cek duplikasi lagu
def check_duplicate_song(judul, artis):
    """Cek duplikasi dengan similarity check"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Cek exact match dulu
            cursor.execute("""
                SELECT id FROM lagu 
                WHERE LOWER(judul) = LOWER(%s) 
                AND LOWER(artis) = LOWER(%s)
                LIMIT 1
            """, (judul, artis))
            if cursor.fetchone():
                return True
            
            # 2. Cek judul yang mirip (untuk menghindari versi berbeda)
            cursor.execute("""
                SELECT id FROM lagu 
                WHERE SOUNDEX(judul) = SOUNDEX(%s)
                AND artis LIKE %s
                LIMIT 1
            """, (judul, f"%{artis}%"))
            return cursor.fetchone() is not None
    finally:
        conn.close()

# Function untuk mengambil hasil pencarian dari YouTube
def search_youtube(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '/tmp/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': '/usr/bin/ffmpeg',  # Sesuaikan dengan path ffmpeg Anda
        'quiet': False,  # Untuk debugging
        'no_warnings': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if 'entries' in info:
                return info['entries'][0]
            return info
    except Exception as e:
        logger.error(f"Error searching YouTube: {str(e)}")
        return None

# Fungsi untuk mendownload dan menyimpan lagu ke database
def download_and_save_song(youtube_url):
    ydl_opts = {
        'quiet': True,
        'extract_audio': True,
        'audio_format': 'mp3',
        'outtmpl': '/tmp/%(id)s.%(ext)s',  # Simpan file sementara
        'postprocessors': [{
            'key': 'FFmpegAudioConvertor',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        file_path = f"/tmp/{info['id']}.mp3"  # Path file yang diunduh
        file_name = f"{info['id']}.mp3"

        # Simpan file audio ke direktori audio
        target_dir = 'static/audio'
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        shutil.move(file_path, os.path.join(target_dir, file_name))

        # Simpan metadata lagu ke database
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lagu (judul, artis, deskripsi, nama_file_audio, thumbnail, tanggal_upload)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (info['title'], info['uploader'], info.get('description', 'No description'), file_name, info['thumbnail'], datetime.now()))
        conn.commit()
        conn.close()

        return file_name

def get_youtube_metadata(youtube_url):
    """Ambil metadata dari video YouTube menggunakan YouTube Data API v3"""
    try:
        api_key = os.getenv("YOUTUBE_API_KEY")
        video_id = extract_video_id(youtube_url)
        if not video_id:
            logger.error("Gagal ekstrak video ID dari URL")
            return None

        youtube = build('youtube', 'v3', developerKey=api_key)
        request = youtube.videos().list(
            part='snippet',
            id=video_id
        )
        response = request.execute()

        if not response['items']:
            logger.error("Video tidak ditemukan di YouTube API")
            return None

        item = response['items'][0]
        snippet = item['snippet']
        deskripsi = snippet.get('description', 'Tidak ada deskripsi')
        if len(deskripsi) > 200:
            deskripsi = deskripsi[:200] + '...'

        logger.info(f"Berhasil ambil metadata: {snippet.get('title')}")

        return {
            'judul': snippet.get('title', ''),
            'artis': snippet.get('channelTitle', ''),
            'deskripsi': deskripsi,
            'thumbnail_url': snippet['thumbnails']['high']['url']
        }

    except Exception as e:
        logger.error(f"Error YouTube API: {e}")
        return None

def get_spotify_metadata(spotify_url):
    """Ambil metadata lagu dari Spotify"""
    try:
        # Ambil ID lagu dari URL
        track_id = spotify_url.split('/')[-1].split('?')[0]

        # Ambil data lagu dari API Spotify
        track = sp.track(track_id)

        judul = track.get('name', 'Judul Tidak Diketahui')
        artis = ', '.join([artist.get('name', 'Unknown Artist') for artist in track.get('artists', [])])
        album = track.get('album', {}).get('name', 'Album Tidak Diketahui')
        release_date = track.get('album', {}).get('release_date', '0000')[:4]
        images = track.get('album', {}).get('images', [])
        cover_url = images[0]['url'] if images else None

        return {
            'judul': judul,
            'artis': artis,
            'album': album,
            'release_date': release_date,
            'cover_url': cover_url
        }

    except Exception as e:
        logger.error(f"❌ Error getting Spotify metadata: {e}")
        return None

def download_thumbnail_async(url, path):
    """Download thumbnail secara async"""
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        print(f"Gagal download thumbnail: {e}")

def download_from_spotify(spotify_url):
    """Download lagu dari Spotify dengan deteksi genre Indonesia dan cek duplikasi"""
    try:
        start_time = time.time()
        metadata = get_spotify_metadata_cached(spotify_url)
        if not metadata:
            return None, "❌ Gagal mendapatkan metadata dari Spotify"

        judul = metadata.get('judul') or "Judul Tidak Diketahui"
        artis = metadata.get('artis') or "Artis Tidak Diketahui"
        album = metadata.get('album') or "Album Tidak Diketahui"
        release_date = metadata.get('release_date') or "Tanggal Tidak Diketahui"
        cover_url = metadata.get('cover_url')

        # 1. Cek duplikasi sebelum download
        if check_duplicate_song(judul, artis):
            return None, "❌ Lagu ini sudah ada di database (duplikat)"

        # 2. Deteksi genre Indonesia (daftar keywords lebih lengkap)
        genre = 'international'
        indonesian_keywords = [
        # Negara dan umum
        'indonesia', 'indo', 'nusantara', 'tanah air', 'ibu pertiwi',

        # Kata Baku (Formal)
        'abjad', 'absorpsi', 'adab', 'adhesi', 'adibusana', 'adidaya', 'afdal', 'aktif', 'aktivitas',
        'analisis', 'andal', 'antre', 'apotek', 'asas', 'atlet', 'autentik', 'azan', 'balig',
        'batalion', 'baterai', 'bazar', 'bengkel', 'beranda', 'berita', 'bioskop', 'busana', 
        'cendekia', 'cermat', 'cerpen', 'daftar', 'definisi', 'demokrasi', 'diagnosis', 'editor',
        'efektif', 'efisien', 'ekonomi', 'ekosistem', 'elastis', 'elektronika', 'evaluasi', 'faktor',
        'fasilitas', 'filosofi', 'formal', 'fotografi', 'galeri', 'gizi', 'globalisasi', 'grafik',
        'hakikat', 'harmoni', 'hemat', 'hipotesis', 'identitas', 'ideologi', 'ilustrasi', 
        'imajinasi', 'implementasi', 'indikator', 'inovasi', 'inspirasi', 'integritas', 'interaksi',
        'investasi', 'jadwal', 'jurnal', 'kader', 'kreativitas', 'kualitas', 'kuantitas', 'laba',
        'laboratorium', 'legitimasi', 'literasi', 'logika', 'manajemen', 'manipulasi', 'metafora',
        'metodologi', 'motivasi', 'narasi', 'negosiasi', 'objektif', 'observasi', 'optimasi',
        'organisasi', 'paradigma', 'partisipasi', 'penalaran', 'pendidikan', 'pengaruh', 'persepsi',
        'prioritas', 'proaktif', 'progresif', 'prosedur', 'rasional', 'realisasi', 'reformasi',
        'regulasi', 'relevansi', 'resolusi', 'responsif', 'risiko', 'sanksi', 'sarana', 'sastra',
        'sistematis', 'solusi', 'strategi', 'struktur', 'subjektif', 'sukses', 'sumber daya',
        'suplemen', 'sustainabilitas', 'teknologi', 'terintegrasi', 'transparansi', 'tuntas',
        'validasi', 'variabel', 'verifikasi', 'visi', 'vitalitas', 'wacana', 'wawasan', 'wilayah',
        'yuridis', 'zona',

        # Kata Tidak Baku/Slang
        'abis', 'aja', 'ampe', 'banget', 'bencong', 'bokap', 'bonyok', 'cewek', 'cowok', 'dong', 
        'gak', 'gitu', 'gue', 'jomblo', 'kamu', 'kek', 'laper', 'lebay', 'loe', 'mager', 'makan', 
        'mantul', 'ngebut', 'nongkrong', 'nyokap', 'pake', 'parah', 'pede', 'pelit', 'pengen', 
        'resek', 'santai', 'selo', 'seru', 'sok', 'syantik', 'tajir', 'telat', 'temen', 'terus', 
        'udah', 'woles', 'yaudah', 'yoi', 'asek', 'asoy', 'baper', 'bau tanah', 'berisik', 
        'biang kerok', 'capek', 'caper', 'cie', 'cupu', 'cuy', 'demen', 'doyan', 'duduk perkara', 
        'dugem', 'edan', 'emang', 'enak aja', 'galau', 'gaul', 'gengsi', 'gokil', 'gue banget', 
        'hangat-hangat tahi ayam', 'ikrib', 'ilfeel', 'jadul', 'jamet', 'jayus', 'kepo', 'kudet', 
        'lebay', 'lo', 'lucu', 'mantan', 'melas', 'modis', 'muda-mudi', 'ngab', 'ngaret', 'ngedate', 
        'ngeri', 'ngopi', 'ngotot', 'ngegas', 'nyantai', 'nyebelin', 'panik', 'pecicilan', 'pelakor', 
        'penasaran', 'pinter', 'rame', 'receh', 'rempong', 'rileks', 'salah tingkah', 'sangar', 
        'sensi', 'sepik', 'sirik', 'sombong', 'sudah', 'suka-suka', 'syok', 'tampang', 'tengil', 
        'terlalu', 'terpesona', 'tukang gosip', 'wibu', 'yang penting hepi', 'zoomer',

        # Tambahan Kosakata Umum
        'abadi', 'acara', 'adil', 'agama', 'air', 'ajaib', 'akal', 'akar', 'akhirat', 'alam', 
        'alasan', 'alat', 'aliran', 'allah', 'aman', 'anak', 'angin', 'angkat', 'antara', 'api', 
        'arah', 'artikel', 'arus', 'asal', 'asam', 'asap', 'asing', 'awan', 'awal', 'ayah', 
        'badan', 'bagus', 'bahagia', 'bahasa', 'bahan', 'bahaya', 'baik', 'baju', 'bakti', 'balik', 
        'ban', 'bangsa', 'bantah', 'barang', 'baru', 'basah', 'batas', 'batu', 'bau', 'bawa', 
        'bayar', 'bayi', 'beda', 'belajar', 'belanja', 'beli', 'benar', 'bencana', 'benda', 'bentuk', 
        'berat', 'beri', 'besar', 'betul', 'biar', 'biasa', 'bibir', 'bicara', 'bidang', 'biji', 
        'bila', 'bilang', 'bingung', 'bisa', 'bising', 'bisu', 'bohong', 'bola', 'bom', 'buku', 
        'bulan', 'bulu', 'bumi', 'bunga', 'buruk', 'burung', 'butuh', 'cabang', 'cahaya', 'cair', 
        'cakap', 'calon', 'cari', 'catat', 'cegah', 'cepat', 'cerah', 'cerita', 'cetak', 'cicil', 
        'cium', 'coba', 'cuaca', 'cukup', 'cuma', 'dalam', 'damai', 'dapat', 'darah', 'dasar', 
        'datang', 'daun', 'debat', 'dekat', 'delapan', 'dengar', 'dengan', 'depan', 'desa', 'detail', 
        'dewa', 'diary', 'diri', 'doa', 'dosa', 'dua', 'duduk', 'dunia', 'dukung', 'dulu', 
        'empat', 'enak', 'energi', 'enggak', 'entah', 'esok', 'fakta', 'fana', 'fantasi', 'foto', 
        'gabung', 'gaji', 'gambar', 'ganti', 'garis', 'gelap', 'gembira', 'gempa', 'generasi', 'genius', 
        'genting', 'gerak', 'gigi', 'gila', 'gol', 'guling', 'guru', 'habis', 'hadiah', 'hadir', 
        'hafal', 'halaman', 'halu', 'hamba', 'hancur', 'hangat', 'hantu', 'harap', 'harga', 'hari', 
        'harus', 'hati', 'heboh', 'helikopter', 'hemat', 'henti', 'heran', 'hidup', 'hijau', 'hilang', 
        'hitung', 'hormat', 'hubung', 'hujan', 'hukum', 'hutan', 'ia', 'ibadah', 'ibu', 'ide', 
        'ikut', 'ilmu', 'iman', 'indah', 'ingat', 'ingin', 'ini', 'insaf', 'intan', 'istana', 
        'istri', 'itu', 'jaga', 'jalan', 'jangan', 'janji', 'jarang', 'jauh', 'jawab', 'jelek', 
        'jelas', 'jembatan', 'jepang', 'jual', 'juara', 'jujur', 'jumpa', 'juta', 'kabar', 'kaget', 
        'kakak', 'kalah', 'kalau', 'kali', 'kamar', 'kampus', 'kantor', 'kapal', 'karya', 'kata', 
        'kaya', 'kayu', 'keadaan', 'kebal', 'kecil', 'kedinginan', 'kehendak', 'kejam', 'keju', 'kelas', 
        'keluar', 'kemana', 'kembang', 'kembar', 'kena', 'kenal', 'kenangan', 'kencan', 'kencing', 'kepala', 
        'kerja', 'kertas', 'kesehatan', 'ketawa', 'ketua', 'khas', 'kiamat', 'kiri', 'kisah', 'kita', 
        'kiwi', 'koin', 'kokoh', 'kolam', 'komik', 'kongres', 'koran', 'kosong', 'kotor', 'kuat', 
        'kucing', 'kuku', 'kulit', 'kunci', 'kurang', 'laku', 'lalu', 'lama', 'lambat', 'lampu', 
        'langit', 'lanjut', 'laut', 'layar', 'lengan', 'lepas', 'lima', 'lipat', 'logam', 'lompat', 
        'lucu', 'lupa', 'mabuk', 'madu', 'mahal', 'makanan', 'malam', 'malu', 'mampu', 'mana', 
        'mata', 'mawar', 'media', 'meja', 'melodi', 'membaca', 'menang', 'menara', 'mengerti', 'mentah', 
        'merah', 'mesin', 'mimpi', 'minum', 'mobil', 'monyet', 'mulai', 'murah', 'musik', 'naik', 
        'nakal', 'nama', 'nasi', 'negara', 'nenek', 'niat', 'nyaman', 'nyanyi', 'obat', 'olahraga', 
        'omong', 'orang', 'otak', 'pacar', 'pada', 'pagi', 'paham', 'pakaian', 'paling', 'panas', 
        'pandai', 'pangeran', 'pantai', 'papan', 'paru', 'pasir', 'pasti', 'patah', 'paus', 'pedang', 
        'pegang', 'peka', 'pelajaran', 'pelukan', 'pena', 'pensiun', 'penting', 'perang', 'pergi', 'perhiasan', 
        'perlu', 'permisi', 'persis', 'pertama', 'pesan', 'pesta', 'pikir', 'pintar', 'pintu', 'pisang', 
        'pohon', 'pokok', 'polisi', 'pulang', 'punya', 'putih', 'putra', 'radio', 'ragu', 'rahasia', 
        'raja', 'rambut', 'ramping', 'rasa', 'rawat', 'rendah', 'ribut', 'ringan', 'roboh', 'rokok', 
        'ruang', 'rugi', 'rumah', 'rumpun', 'rusak', 'sabar', 'sahabat', 'sakit', 'salah', 'sama', 
        'sampai', 'sampah', 'sandal', 'sangat', 'sapi', 'sarapan', 'satu', 'sawah', 'sayang', 'sayur', 
        'sebab', 'sebelah', 'sebut', 'sedang', 'sedih', 'segala', 'sehat', 'sejarah', 'sejuk', 'sekolah', 
        'selalu', 'selamat', 'selera', 'selesai', 'sembuh', 'sempurna', 'senang', 'seni', 'sentuh', 'sepak', 
        'sepeda', 'seperti', 'seragam', 'serius', 'sering', 'susah', 'syukur', 'tabung', 'tahan', 'tahu', 
        'takut', 'taman', 'tambah', 'tampil', 'tanah', 'tangan', 'tanya', 'tapi', 'tarik', 'tawa', 
        'tebal', 'tegang', 'tegas', 'tekan', 'telinga', 'telur', 'teman', 'tembak', 'tembok', 'tempat', 
        'tenang', 'tenda', 'tentang', 'tepat', 'terang', 'terbang', 'terima', 'terus', 'tetap', 'tidur', 
        'tiga', 'tikus', 'timur', 'tinggi', 'titik', 'tolong', 'tua', 'tulis', 'tunggu', 'uang', 
        'ubur', 'ujung', 'ular', 'umur', 'undang', 'untuk', 'urus', 'usia', 'utama', 'wajah', 
        'waktu', 'wanita', 'warna', 'warta', 'ya', 'yakin', 'yatim', 'zaman', 'zat'
            
        # Provinsi dan kota
        'aceh', 'medan', 'padang', 'palembang', 'lampung', 'bengkulu', 
        'jambi', 'riau', 'pekanbaru', 'batam', 'jakarta', 'bogor',
        'depok', 'tanggerang', 'bekasi', 'bandung', 'jawa barat', 
        'jawa tengah', 'jawa timur', 'yogyakarta', 'surabaya', 'semarang',
        'bali', 'denpasar', 'lombok', 'ntb', 'nusa tenggara', 'kalimantan',
        'borneo', 'sulawesi', 'makassar', 'manado', 'toraja', 'papua',
        'ambon', 'maluku', 'ternate', 'tidore',
        
        # Suku dan budaya
        'jawa', 'sunda', 'batak', 'minang', 'dayak', 'betawi', 'baduy',
        'banjar', 'bugis', 'makassar', 'toraja', 'asmat', 'dani', 'ambon',
        'aceh', 'gayo', 'nias', 'mentawai', 'sasak', 'bima', 'dompu',
        
        # Genre musik
        'dangdut', 'koplo', 'campursari', 'keroncong', 'gamelan', 'jaipong',
        'tarling', 'degung', 'kecapi', 'angklung', 'sasando', 'gambang kromong',
        'tanjidor', 'gondang', 'gandrung', 'joget', 'zapin', 'samrah', 'hadrah',
        'qasidah', 'gambus', 'orkes melayu', 'langgam jawa',
        
        # Penyanyi/band terkenal
        'nike ardilla', 'sheila on 7', 'dmasiv', 'noah', 'peterpan', 'ungu',
        'slank', 'kangen band', 'wali', 'armada', 'setia band', 'geisha',
        'jikustik', 'dewa 19', 'kota', 'kla project', 'bunga citra lestari',
        'agnes mo', 'rossa', 'krisdayanti', 'titi dj', 'ruth sahanaya',
        'andre hehanussa', 'vina panduwinata', 'betharia sonata', 'iwan fals',
        'gombloh', 'ebiet g ade', 'chrisye', 'didi kempot', 'suzanna',
        'alm. rhoma irama', 'soneta group', 'mansyur s', 'meggy z',
        'ita purnamasari', 'viera',

        # Tambahan lainnya
        'nidji', 'letto', 'seventeen', 'lyla', 'ada band', 'five minutes',
        'last child', 'anji', 'glen fredly', 'mahalini', 'tiara andini',
        'judika', 'ariel noah', 'afgan', 'rizky febian', 'tulus', 'yura yunita',
        'marion jola', 'via vallen', 'nella kharisma', 'happy asmara',
        'nissa sabyan', 'sabyan gambus', 'dangdut koplo', 'denny caknan',
        'trio macan', 'tasya rosmala', 'erlando', 'bebi romeo',
        'melly goeslaw', 'republic', 'drive', 'element', 'the rain',
        'kotak', 'cokelat', 'sheila majid', 'gita gutawa', 'delon', 'mellyana manuhutu',
        'yovie widiyanto', 'yovie & nuno', 'the overtunes', 'rafly', 'samsons'
            
        # Lagu daerah
        'bubuy bulan', 'manuk dadali', 'es lilin', 'tokecang', 'soleram',
        'ampar ampar pisang', 'gundul pacul', 'suwe ora jamu', 'gambang suling',
        'jali-jali', 'kicir-kicir', 'lenong', 'ondel-ondel', 'kroncong moritsko',
        
        # Nama khas Indonesia
        'wayang', 'batik', 'borobudur', 'prambanan', 'bali', 'komodo',
        'rendang', 'sate', 'nasi goreng', 'gado-gado', 'keris', 'kujang',
        
        # Pola nama orang Indonesia
        r'(^|\s)(wan|wati|sari|putri|putra|jaya|adi|surya|wijaya|tanjung)',
        r'(siregar|nasution|sinaga|harahap|ginting|sitepu|manik|nainggolan)',
        r'(pane|marpaung|hutagalung|pasaribu|simbolon|sihombing|panggabean)',
        r'(nadeak|sitorus|butar-butar|sembiring|tarigan|perangin-angin)',
        r'(silalahi|tamba|hutapea|pangaribuan|tarihoran|pangihutan)',
        r'(halim|wibowo|gunawan|kusuma|setiawan|santoso|wijaya|yulianto)']

        title_check = judul.lower()
        artist_check = artis.lower()
        
        # Cek kombinasi judul + artis
        combined_check = f"{title_check} {artist_check}"
        
        # Deteksi berdasarkan berbagai pola
        if (any(keyword in title_check for keyword in indonesian_keywords) or
            any(keyword in artist_check for keyword in indonesian_keywords) or
            any(keyword in combined_check for keyword in indonesian_keywords) or
            # Deteksi pola nama khas Indonesia
            re.search(r'(^|\s)(wan|wati|sari|putri|putra|jaya|adi|surya|wijaya|tanjung|siregar|nasution|sinaga|harahap|ginting|sitepu|manik|nainggolan|pane|marpaung|hutagalung|pasaribu|simbolon|sihombing|panggabean|nadeak|sitorus|butar-butar|sembiring|tarigan|perangin-angin|sinurat|sitohang|turnip|marbun|dongoran|rajagukguk|pohan|silalahi|tamba|hutapea|pangaribuan|tarihoran|pangihutan|hutajulu|hutauruk|hutabarat|hutasoit|hutagaol|hutapea|siagian|sianipar|sibuea|sibagariang|sitompul|sihotang|hasibuan|lubis|tanoto|lim|tjahjadi|wibowo|wongso|gunawan|kusuma|setiawan|santoso|wijaya|yulianto|suryadi|handoko|budiman|hartanto|halim|siregar|napitupulu|pangestu|wibisono|susanto|saputra|siregar|wijaya|santoso|halim|wibowo|gunawan|kusuma|setiawan|yulianto|suryadi|handoko|budiman|hartanto|galau|sedih|saya|sebelum|sesudah)($|\s)', artist_check)):
            genre = 'indonesian'
            logger.info(f"Detected Indonesian song: {judul} - {artis}")

        print(f"Spotify metadata processed in {time.time() - start_time:.2f}s")
        
        # 3. Cari di YouTube dengan query optimal
        search_query = f"{judul} {artis} official audio"
        youtube_url = search_youtube(search_query)

        if not youtube_url:
            return None, "❌ Tidak dapat menemukan lagu di YouTube berdasarkan metadata Spotify"

        deskripsi = f"🎵 Dari Spotify\nAlbum: {album}\nRilis: {release_date}\nGenre: {genre}"
        
        # 4. Download dari YouTube dengan info genre
        return download_from_youtube(
            youtube_url=youtube_url,
            judul=judul,
            artis=artis,
            deskripsi=deskripsi,
            thumbnail_url=cover_url,
            genre=genre  # Kirim genre yang sudah dideteksi
        )

    except Exception as e:
        logger.error(f"Error processing Spotify track: {e}")
        return None, f"❌ Terjadi kesalahan saat memproses lagu dari Spotify: {str(e)}"

def download_from_youtube(youtube_url, judul=None, artis=None, deskripsi=None, thumbnail_url=None, genre=None):
    """Download lagu dari YouTube dengan deteksi genre Indonesia dan cek duplikasi"""
    try:
        start_time = time.time()
        
        # 1. Ambil metadata otomatis jika tidak disediakan
        if not judul or not artis:
            yt_metadata = get_youtube_metadata_cached(youtube_url)
            if yt_metadata:
                judul = judul or yt_metadata.get('judul') or "Judul Tidak Diketahui"
                artis = artis or yt_metadata.get('artis') or "Artis Tidak Diketahui"
                deskripsi = deskripsi or yt_metadata.get('deskripsi') or "Tidak ada deskripsi"
                thumbnail_url = thumbnail_url or yt_metadata.get('thumbnail_url')

        # Gunakan default jika masih kosong
        judul = judul or "Judul Tidak Diketahui"
        artis = artis or "Artis Tidak Diketahui"
        deskripsi = deskripsi or "Tidak ada deskripsi"

        # 2. Cek duplikasi sebelum download
        if check_duplicate_song(judul, artis):
            return None, "❌ Lagu ini sudah ada di database (duplikat)"

        # 3. Deteksi genre Indonesia jika tidak disediakan
        if genre is None:
            genre = 'international'
            indonesian_keywords = [
        # Negara dan umum
        'indonesia', 'indo', 'nusantara', 'tanah air', 'ibu pertiwi',

        # Kata Baku (Formal)
        'abjad', 'absorpsi', 'adab', 'adhesi', 'adibusana', 'adidaya', 'afdal', 'aktif', 'aktivitas',
        'analisis', 'andal', 'antre', 'apotek', 'asas', 'atlet', 'autentik', 'azan', 'balig',
        'batalion', 'baterai', 'bazar', 'bengkel', 'beranda', 'berita', 'bioskop', 'busana', 
        'cendekia', 'cermat', 'cerpen', 'daftar', 'definisi', 'demokrasi', 'diagnosis', 'editor',
        'efektif', 'efisien', 'ekonomi', 'ekosistem', 'elastis', 'elektronika', 'evaluasi', 'faktor',
        'fasilitas', 'filosofi', 'formal', 'fotografi', 'galeri', 'gizi', 'globalisasi', 'grafik',
        'hakikat', 'harmoni', 'hemat', 'hipotesis', 'identitas', 'ideologi', 'ilustrasi', 
        'imajinasi', 'implementasi', 'indikator', 'inovasi', 'inspirasi', 'integritas', 'interaksi',
        'investasi', 'jadwal', 'jurnal', 'kader', 'kreativitas', 'kualitas', 'kuantitas', 'laba',
        'laboratorium', 'legitimasi', 'literasi', 'logika', 'manajemen', 'manipulasi', 'metafora',
        'metodologi', 'motivasi', 'narasi', 'negosiasi', 'objektif', 'observasi', 'optimasi',
        'organisasi', 'paradigma', 'partisipasi', 'penalaran', 'pendidikan', 'pengaruh', 'persepsi',
        'prioritas', 'proaktif', 'progresif', 'prosedur', 'rasional', 'realisasi', 'reformasi',
        'regulasi', 'relevansi', 'resolusi', 'responsif', 'risiko', 'sanksi', 'sarana', 'sastra',
        'sistematis', 'solusi', 'strategi', 'struktur', 'subjektif', 'sukses', 'sumber daya',
        'suplemen', 'sustainabilitas', 'teknologi', 'terintegrasi', 'transparansi', 'tuntas',
        'validasi', 'variabel', 'verifikasi', 'visi', 'vitalitas', 'wacana', 'wawasan', 'wilayah',
        'yuridis', 'zona',

        # Kata Tidak Baku/Slang
        'abis', 'aja', 'ampe', 'banget', 'bencong', 'bokap', 'bonyok', 'cewek', 'cowok', 'dong', 
        'gak', 'gitu', 'gue', 'jomblo', 'kamu', 'kek', 'laper', 'lebay', 'loe', 'mager', 'makan', 
        'mantul', 'ngebut', 'nongkrong', 'nyokap', 'pake', 'parah', 'pede', 'pelit', 'pengen', 
        'resek', 'santai', 'selo', 'seru', 'sok', 'syantik', 'tajir', 'telat', 'temen', 'terus', 
        'udah', 'woles', 'yaudah', 'yoi', 'asek', 'asoy', 'baper', 'bau tanah', 'berisik', 
        'biang kerok', 'capek', 'caper', 'cie', 'cupu', 'cuy', 'demen', 'doyan', 'duduk perkara', 
        'dugem', 'edan', 'emang', 'enak aja', 'galau', 'gaul', 'gengsi', 'gokil', 'gue banget', 
        'hangat-hangat tahi ayam', 'ikrib', 'ilfeel', 'jadul', 'jamet', 'jayus', 'kepo', 'kudet', 
        'lebay', 'lo', 'lucu', 'mantan', 'melas', 'modis', 'muda-mudi', 'ngab', 'ngaret', 'ngedate', 
        'ngeri', 'ngopi', 'ngotot', 'ngegas', 'nyantai', 'nyebelin', 'panik', 'pecicilan', 'pelakor', 
        'penasaran', 'pinter', 'rame', 'receh', 'rempong', 'rileks', 'salah tingkah', 'sangar', 
        'sensi', 'sepik', 'sirik', 'sombong', 'sudah', 'suka-suka', 'syok', 'tampang', 'tengil', 
        'terlalu', 'terpesona', 'tukang gosip', 'wibu', 'yang penting hepi', 'zoomer',

        # Tambahan Kosakata Umum
        'abadi', 'acara', 'adil', 'agama', 'air', 'ajaib', 'akal', 'akar', 'akhirat', 'alam', 
        'alasan', 'alat', 'aliran', 'allah', 'aman', 'anak', 'angin', 'angkat', 'antara', 'api', 
        'arah', 'artikel', 'arus', 'asal', 'asam', 'asap', 'asing', 'awan', 'awal', 'ayah', 
        'badan', 'bagus', 'bahagia', 'bahasa', 'bahan', 'bahaya', 'baik', 'baju', 'bakti', 'balik', 
        'ban', 'bangsa', 'bantah', 'barang', 'baru', 'basah', 'batas', 'batu', 'bau', 'bawa', 
        'bayar', 'bayi', 'beda', 'belajar', 'belanja', 'beli', 'benar', 'bencana', 'benda', 'bentuk', 
        'berat', 'beri', 'besar', 'betul', 'biar', 'biasa', 'bibir', 'bicara', 'bidang', 'biji', 
        'bila', 'bilang', 'bingung', 'bisa', 'bising', 'bisu', 'bohong', 'bola', 'bom', 'buku', 
        'bulan', 'bulu', 'bumi', 'bunga', 'buruk', 'burung', 'butuh', 'cabang', 'cahaya', 'cair', 
        'cakap', 'calon', 'cari', 'catat', 'cegah', 'cepat', 'cerah', 'cerita', 'cetak', 'cicil', 
        'cium', 'coba', 'cuaca', 'cukup', 'cuma', 'dalam', 'damai', 'dapat', 'darah', 'dasar', 
        'datang', 'daun', 'debat', 'dekat', 'delapan', 'dengar', 'dengan', 'depan', 'desa', 'detail', 
        'dewa', 'diary', 'diri', 'doa', 'dosa', 'dua', 'duduk', 'dunia', 'dukung', 'dulu', 
        'empat', 'enak', 'energi', 'enggak', 'entah', 'esok', 'fakta', 'fana', 'fantasi', 'foto', 
        'gabung', 'gaji', 'gambar', 'ganti', 'garis', 'gelap', 'gembira', 'gempa', 'generasi', 'genius', 
        'genting', 'gerak', 'gigi', 'gila', 'gol', 'guling', 'guru', 'habis', 'hadiah', 'hadir', 
        'hafal', 'halaman', 'halu', 'hamba', 'hancur', 'hangat', 'hantu', 'harap', 'harga', 'hari', 
        'harus', 'hati', 'heboh', 'helikopter', 'hemat', 'henti', 'heran', 'hidup', 'hijau', 'hilang', 
        'hitung', 'hormat', 'hubung', 'hujan', 'hukum', 'hutan', 'ia', 'ibadah', 'ibu', 'ide', 
        'ikut', 'ilmu', 'iman', 'indah', 'ingat', 'ingin', 'ini', 'insaf', 'intan', 'istana', 
        'istri', 'itu', 'jaga', 'jalan', 'jangan', 'janji', 'jarang', 'jauh', 'jawab', 'jelek', 
        'jelas', 'jembatan', 'jepang', 'jual', 'juara', 'jujur', 'jumpa', 'juta', 'kabar', 'kaget', 
        'kakak', 'kalah', 'kalau', 'kali', 'kamar', 'kampus', 'kantor', 'kapal', 'karya', 'kata', 
        'kaya', 'kayu', 'keadaan', 'kebal', 'kecil', 'kedinginan', 'kehendak', 'kejam', 'keju', 'kelas', 
        'keluar', 'kemana', 'kembang', 'kembar', 'kena', 'kenal', 'kenangan', 'kencan', 'kencing', 'kepala', 
        'kerja', 'kertas', 'kesehatan', 'ketawa', 'ketua', 'khas', 'kiamat', 'kiri', 'kisah', 'kita', 
        'kiwi', 'koin', 'kokoh', 'kolam', 'komik', 'kongres', 'koran', 'kosong', 'kotor', 'kuat', 
        'kucing', 'kuku', 'kulit', 'kunci', 'kurang', 'laku', 'lalu', 'lama', 'lambat', 'lampu', 
        'langit', 'lanjut', 'laut', 'layar', 'lengan', 'lepas', 'lima', 'lipat', 'logam', 'lompat', 
        'lucu', 'lupa', 'mabuk', 'madu', 'mahal', 'makanan', 'malam', 'malu', 'mampu', 'mana', 
        'mata', 'mawar', 'media', 'meja', 'melodi', 'membaca', 'menang', 'menara', 'mengerti', 'mentah', 
        'merah', 'mesin', 'mimpi', 'minum', 'mobil', 'monyet', 'mulai', 'murah', 'musik', 'naik', 
        'nakal', 'nama', 'nasi', 'negara', 'nenek', 'niat', 'nyaman', 'nyanyi', 'obat', 'olahraga', 
        'omong', 'orang', 'otak', 'pacar', 'pada', 'pagi', 'paham', 'pakaian', 'paling', 'panas', 
        'pandai', 'pangeran', 'pantai', 'papan', 'paru', 'pasir', 'pasti', 'patah', 'paus', 'pedang', 
        'pegang', 'peka', 'pelajaran', 'pelukan', 'pena', 'pensiun', 'penting', 'perang', 'pergi', 'perhiasan', 
        'perlu', 'permisi', 'persis', 'pertama', 'pesan', 'pesta', 'pikir', 'pintar', 'pintu', 'pisang', 
        'pohon', 'pokok', 'polisi', 'pulang', 'punya', 'putih', 'putra', 'radio', 'ragu', 'rahasia', 
        'raja', 'rambut', 'ramping', 'rasa', 'rawat', 'rendah', 'ribut', 'ringan', 'roboh', 'rokok', 
        'ruang', 'rugi', 'rumah', 'rumpun', 'rusak', 'sabar', 'sahabat', 'sakit', 'salah', 'sama', 
        'sampai', 'sampah', 'sandal', 'sangat', 'sapi', 'sarapan', 'satu', 'sawah', 'sayang', 'sayur', 
        'sebab', 'sebelah', 'sebut', 'sedang', 'sedih', 'segala', 'sehat', 'sejarah', 'sejuk', 'sekolah', 
        'selalu', 'selamat', 'selera', 'selesai', 'sembuh', 'sempurna', 'senang', 'seni', 'sentuh', 'sepak', 
        'sepeda', 'seperti', 'seragam', 'serius', 'sering', 'susah', 'syukur', 'tabung', 'tahan', 'tahu', 
        'takut', 'taman', 'tambah', 'tampil', 'tanah', 'tangan', 'tanya', 'tapi', 'tarik', 'tawa', 
        'tebal', 'tegang', 'tegas', 'tekan', 'telinga', 'telur', 'teman', 'tembak', 'tembok', 'tempat', 
        'tenang', 'tenda', 'tentang', 'tepat', 'terang', 'terbang', 'terima', 'terus', 'tetap', 'tidur', 
        'tiga', 'tikus', 'timur', 'tinggi', 'titik', 'tolong', 'tua', 'tulis', 'tunggu', 'uang', 
        'ubur', 'ujung', 'ular', 'umur', 'undang', 'untuk', 'urus', 'usia', 'utama', 'wajah', 
        'waktu', 'wanita', 'warna', 'warta', 'ya', 'yakin', 'yatim', 'zaman', 'zat'
            
        # Provinsi dan kota
        'aceh', 'medan', 'padang', 'palembang', 'lampung', 'bengkulu', 
        'jambi', 'riau', 'pekanbaru', 'batam', 'jakarta', 'bogor',
        'depok', 'tanggerang', 'bekasi', 'bandung', 'jawa barat', 
        'jawa tengah', 'jawa timur', 'yogyakarta', 'surabaya', 'semarang',
        'bali', 'denpasar', 'lombok', 'ntb', 'nusa tenggara', 'kalimantan',
        'borneo', 'sulawesi', 'makassar', 'manado', 'toraja', 'papua',
        'ambon', 'maluku', 'ternate', 'tidore',
        
        # Suku dan budaya
        'jawa', 'sunda', 'batak', 'minang', 'dayak', 'betawi', 'baduy',
        'banjar', 'bugis', 'makassar', 'toraja', 'asmat', 'dani', 'ambon',
        'aceh', 'gayo', 'nias', 'mentawai', 'sasak', 'bima', 'dompu',
        
        # Genre musik
        'dangdut', 'koplo', 'campursari', 'keroncong', 'gamelan', 'jaipong',
        'tarling', 'degung', 'kecapi', 'angklung', 'sasando', 'gambang kromong',
        'tanjidor', 'gondang', 'gandrung', 'joget', 'zapin', 'samrah', 'hadrah',
        'qasidah', 'gambus', 'orkes melayu', 'langgam jawa',
        
        # Penyanyi/band terkenal
        'nike ardilla', 'sheila on 7', 'dmasiv', 'noah', 'peterpan', 'ungu',
        'slank', 'kangen band', 'wali', 'armada', 'setia band', 'geisha',
        'jikustik', 'dewa 19', 'kota', 'kla project', 'bunga citra lestari',
        'agnes mo', 'rossa', 'krisdayanti', 'titi dj', 'ruth sahanaya',
        'andre hehanussa', 'vina panduwinata', 'betharia sonata', 'iwan fals',
        'gombloh', 'ebiet g ade', 'chrisye', 'didi kempot', 'suzanna',
        'alm. rhoma irama', 'soneta group', 'mansyur s', 'meggy z',
        'ita purnamasari', 'viera',

        # Tambahan lainnya
        'nidji', 'letto', 'seventeen', 'lyla', 'ada band', 'five minutes',
        'last child', 'anji', 'glen fredly', 'mahalini', 'tiara andini',
        'judika', 'ariel noah', 'afgan', 'rizky febian', 'tulus', 'yura yunita',
        'marion jola', 'via vallen', 'nella kharisma', 'happy asmara',
        'nissa sabyan', 'sabyan gambus', 'dangdut koplo', 'denny caknan',
        'trio macan', 'tasya rosmala', 'erlando', 'bebi romeo',
        'melly goeslaw', 'republic', 'drive', 'element', 'the rain',
        'kotak', 'cokelat', 'sheila majid', 'gita gutawa', 'delon', 'mellyana manuhutu',
        'yovie widiyanto', 'yovie & nuno', 'the overtunes', 'rafly', 'samsons'
            
        # Lagu daerah
        'bubuy bulan', 'manuk dadali', 'es lilin', 'tokecang', 'soleram',
        'ampar ampar pisang', 'gundul pacul', 'suwe ora jamu', 'gambang suling',
        'jali-jali', 'kicir-kicir', 'lenong', 'ondel-ondel', 'kroncong moritsko',
        
        # Nama khas Indonesia
        'wayang', 'batik', 'borobudur', 'prambanan', 'bali', 'komodo',
        'rendang', 'sate', 'nasi goreng', 'gado-gado', 'keris', 'kujang',
        
        # Pola nama orang Indonesia
        r'(^|\s)(wan|wati|sari|putri|putra|jaya|adi|surya|wijaya|tanjung)',
        r'(siregar|nasution|sinaga|harahap|ginting|sitepu|manik|nainggolan)',
        r'(pane|marpaung|hutagalung|pasaribu|simbolon|sihombing|panggabean)',
        r'(nadeak|sitorus|butar-butar|sembiring|tarigan|perangin-angin)',
        r'(silalahi|tamba|hutapea|pangaribuan|tarihoran|pangihutan)',
        r'(halim|wibowo|gunawan|kusuma|setiawan|santoso|wijaya|yulianto)']
            
            title_check = judul.lower()
            artist_check = artis.lower()
            desc_check = deskripsi.lower() if deskripsi else ""
            
            if (any(keyword in title_check for keyword in indonesian_keywords) or
                any(keyword in artist_check for keyword in indonesian_keywords) or
                any(keyword in desc_check for keyword in indonesian_keywords) or
                re.search(r'(^|\s)(wan|wati|sari|putri|putra)($|\s)', artist_check)):
                
                genre = 'indonesian'
                logger.info(f"🇮🇩 Detected Indonesian song: {judul} - {artis}")

        # 4. Persiapkan direktori dan nama file
        audio_dir = os.path.join('data', 'audio')
        thumb_dir = os.path.join('data', 'thumbs')
        os.makedirs(audio_dir, exist_ok=True)
        os.makedirs(thumb_dir, exist_ok=True)

        safe_title = "".join(c if c.isalnum() or c in " -_" else "-" for c in judul)
        video_id = extract_youtube_id(youtube_url) or datetime.now().strftime("%Y%m%d%H%M%S")
        thumb_file = f"{safe_title}-{video_id}.jpg"
        thumb_path = os.path.join(thumb_dir, thumb_file)

        # 5. Download thumbnail
        thumbnail_downloaded = False
        if thumbnail_url:
            try:
                urllib.request.urlretrieve(thumbnail_url, thumb_path)
                thumbnail_downloaded = True
                logger.info(f"Thumbnail downloaded from {thumbnail_url}")
            except Exception as e:
                logger.warning(f"Gagal download thumbnail dari URL: {e}")

        # Fallback ke thumbnail YouTube
        if not thumbnail_downloaded:
            for quality in ['maxresdefault', 'hqdefault']:
                try:
                    yt_thumb = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
                    urllib.request.urlretrieve(yt_thumb, thumb_path)
                    thumbnail_downloaded = True
                    break
                except Exception as e:
                    logger.warning(f"Gagal download thumbnail {quality}: {e}")

        if not os.path.exists(thumb_path):
            return None, "Gagal membuat file thumbnail"

        # 6. Download audio
        output_template = os.path.join(audio_dir, f"{safe_title}-%(id)s.%(ext)s")
        command = [
            'yt-dlp',
            '-x',
            '--audio-format', 'mp3',
            '--audio-quality', '128K',
            '--socket-timeout', '10',
            '--retries', '3',
            '-o', output_template,
            youtube_url
        ]
        
        logger.info(f"Executing: {' '.join(command)}")
        subprocess.run(command, check=True)

        # 7. Cari file yang baru didownload
        downloaded_files = [f for f in os.listdir(audio_dir) if safe_title in f and f.endswith('.mp3')]
        if not downloaded_files:
            return None, 'File audio tidak ditemukan setelah diunduh'
        final_file = downloaded_files[0]

        # 8. Salin thumbnail ke folder public
        public_thumb_dir = os.path.join('public', 'thumbs')
        os.makedirs(public_thumb_dir, exist_ok=True)
        shutil.copyfile(thumb_path, os.path.join(public_thumb_dir, thumb_file))

        # 9. Simpan ke database dengan genre
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO lagu 
                (judul, artis, deskripsi, nama_file_audio, thumbnail, tanggal_upload, genre) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (judul, artis, deskripsi, final_file, thumb_file, datetime.now(), genre)
            )
            conn.commit()
        conn.close()

        logger.info(f"Proses selesai dalam {time.time() - start_time:.2f} detik")

        return {
            'success': True,
            'message': '✅ Lagu berhasil diupload dan disimpan!',
            'judul': judul,
            'artis': artis,
            'deskripsi': deskripsi,
            'thumbnail': f"/public/thumbs/{thumb_file}",
            'genre': genre,
            'audio_file': final_file
        }, None

    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess error: {e}")
        return None, 'Gagal mengunduh audio'
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None, f'Terjadi kesalahan saat upload: {str(e)}'

# funsi playlist

def get_spotify_playlist_tracks(playlist_url):
    """Ambil semua track dari playlist Spotify"""
    try:
        # Decode URL jika ada karakter encoded
        decoded_url = urllib.parse.unquote(playlist_url)
        playlist_id = decoded_url.split('/')[-1].split('?')[0]
        
        # Periksa playlist ID apakah valid
        if not playlist_id:
            logger.error(f"Playlist ID tidak ditemukan dari URL: {playlist_url}")
            return None

        # Minta tracks dari playlist Spotify
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        # Handle pagination jika playlist memiliki lebih dari 100 track
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        
        return [{
            'title': item['track']['name'],
            'artist': ', '.join([artist['name'] for artist in item['track']['artists']]),
            'album': item['track']['album']['name'],
            'cover_url': item['track']['album']['images'][0]['url'] if item['track']['album']['images'] else None,
            'spotify_url': item['track']['external_urls']['spotify']
        } for item in tracks if item['track']]
    except Exception as e:
        logger.error(f"Error getting Spotify playlist: {e}")
        return None

def get_youtube_playlist_videos(playlist_url):
    """Ambil semua video dari playlist YouTube secara aman"""
    try:
        command = [
            'yt-dlp',
            '--flat-playlist',
            '--dump-single-json',
            '--no-warnings',
            playlist_url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"❌ yt-dlp error: {result.stderr.strip()}")
            return None
        
        playlist_data = json.loads(result.stdout)

        entries = playlist_data.get('entries', [])
        videos = []

        for entry in entries:
            video_id = entry.get('id')
            title = entry.get('title', 'Untitled')
            if not video_id:
                continue  # Lewati jika tidak ada ID
            
            videos.append({
                'title': title,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'duration': entry.get('duration', 0)
            })

        return videos if videos else None

    except subprocess.TimeoutExpired:
        logger.error("❌ Timeout saat mengambil data playlist YouTube.")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON error saat parsing output yt-dlp: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error tidak terduga saat mengambil playlist YouTube: {e}")
        return None

def download_playlist(playlist_url):
    """Download seluruh playlist dari Spotify atau YouTube"""
    try:
        if 'spotify.com/playlist' in playlist_url:
            return process_spotify_playlist(playlist_url)
        elif 'youtube.com/playlist' in playlist_url or 'youtu.be/playlist' in playlist_url or 'youtube.com/watch?v=' in playlist_url:
            return process_youtube_playlist(playlist_url)
        elif 'music.youtube.com/playlist' in playlist_url:
            return process_youtube_music_playlist(playlist_url)
        else:
            return None, "❌ Jenis playlist tidak didukung"
    except Exception as e:
        logger.error(f"❌ Error processing playlist: {e}")
        return None, f"Terjadi kesalahan saat memproses playlist: {str(e)}"

def process_spotify_playlist(playlist_url):
    """Proses playlist Spotify dengan deteksi genre Indonesia dan cek duplikasi"""
    tracks = get_spotify_playlist_tracks(playlist_url)
    if not tracks:
        return None, "❌ Gagal mendapatkan track dari playlist Spotify"
    
    results = []
    errors = []
    duplicates = 0
    indonesian_detected = 0
    
    # Daftar keyword untuk deteksi lagu Indonesia (lebih dari 150 keywords)
    indonesian_keywords = [
        # Negara dan umum
        'indonesia', 'indo', 'nusantara', 'tanah air', 'ibu pertiwi',

        # Kata Baku (Formal)
    'abjad', 'absorpsi', 'adab', 'adhesi', 'adibusana', 'adidaya', 'afdal', 'aktif', 'aktivitas',
    'analisis', 'andal', 'antre', 'apotek', 'asas', 'atlet', 'autentik', 'azan', 'balig',
    'batalion', 'baterai', 'bazar', 'bengkel', 'beranda', 'berita', 'bioskop', 'busana', 
    'cendekia', 'cermat', 'cerpen', 'daftar', 'definisi', 'demokrasi', 'diagnosis', 'editor',
    'efektif', 'efisien', 'ekonomi', 'ekosistem', 'elastis', 'elektronika', 'evaluasi', 'faktor',
    'fasilitas', 'filosofi', 'formal', 'fotografi', 'galeri', 'gizi', 'globalisasi', 'grafik',
    'hakikat', 'harmoni', 'hemat', 'hipotesis', 'identitas', 'ideologi', 'ilustrasi', 
    'imajinasi', 'implementasi', 'indikator', 'inovasi', 'inspirasi', 'integritas', 'interaksi',
    'investasi', 'jadwal', 'jurnal', 'kader', 'kreativitas', 'kualitas', 'kuantitas', 'laba',
    'laboratorium', 'legitimasi', 'literasi', 'logika', 'manajemen', 'manipulasi', 'metafora',
    'metodologi', 'motivasi', 'narasi', 'negosiasi', 'objektif', 'observasi', 'optimasi',
    'organisasi', 'paradigma', 'partisipasi', 'penalaran', 'pendidikan', 'pengaruh', 'persepsi',
    'prioritas', 'proaktif', 'progresif', 'prosedur', 'rasional', 'realisasi', 'reformasi',
    'regulasi', 'relevansi', 'resolusi', 'responsif', 'risiko', 'sanksi', 'sarana', 'sastra',
    'sistematis', 'solusi', 'strategi', 'struktur', 'subjektif', 'sukses', 'sumber daya',
    'suplemen', 'sustainabilitas', 'teknologi', 'terintegrasi', 'transparansi', 'tuntas',
    'validasi', 'variabel', 'verifikasi', 'visi', 'vitalitas', 'wacana', 'wawasan', 'wilayah',
    'yuridis', 'zona',

    # Kata Tidak Baku/Slang
    'abis', 'aja', 'ampe', 'banget', 'bencong', 'bokap', 'bonyok', 'cewek', 'cowok', 'dong', 
    'gak', 'gitu', 'gue', 'jomblo', 'kamu', 'kek', 'laper', 'lebay', 'loe', 'mager', 'makan', 
    'mantul', 'ngebut', 'nongkrong', 'nyokap', 'pake', 'parah', 'pede', 'pelit', 'pengen', 
    'resek', 'santai', 'selo', 'seru', 'sok', 'syantik', 'tajir', 'telat', 'temen', 'terus', 
    'udah', 'woles', 'yaudah', 'yoi', 'asek', 'asoy', 'baper', 'bau tanah', 'berisik', 
    'biang kerok', 'capek', 'caper', 'cie', 'cupu', 'cuy', 'demen', 'doyan', 'duduk perkara', 
    'dugem', 'edan', 'emang', 'enak aja', 'galau', 'gaul', 'gengsi', 'gokil', 'gue banget', 
    'hangat-hangat tahi ayam', 'ikrib', 'ilfeel', 'jadul', 'jamet', 'jayus', 'kepo', 'kudet', 
    'lebay', 'lo', 'lucu', 'mantan', 'melas', 'modis', 'muda-mudi', 'ngab', 'ngaret', 'ngedate', 
    'ngeri', 'ngopi', 'ngotot', 'ngegas', 'nyantai', 'nyebelin', 'panik', 'pecicilan', 'pelakor', 
    'penasaran', 'pinter', 'rame', 'receh', 'rempong', 'rileks', 'salah tingkah', 'sangar', 
    'sensi', 'sepik', 'sirik', 'sombong', 'sudah', 'suka-suka', 'syok', 'tampang', 'tengil', 
    'terlalu', 'terpesona', 'tukang gosip', 'wibu', 'yang penting hepi', 'zoomer',

    # Tambahan Kosakata Umum
    'abadi', 'acara', 'adil', 'agama', 'air', 'ajaib', 'akal', 'akar', 'akhirat', 'alam', 
    'alasan', 'alat', 'aliran', 'allah', 'aman', 'anak', 'angin', 'angkat', 'antara', 'api', 
    'arah', 'artikel', 'arus', 'asal', 'asam', 'asap', 'asing', 'awan', 'awal', 'ayah', 
    'badan', 'bagus', 'bahagia', 'bahasa', 'bahan', 'bahaya', 'baik', 'baju', 'bakti', 'balik', 
    'ban', 'bangsa', 'bantah', 'barang', 'baru', 'basah', 'batas', 'batu', 'bau', 'bawa', 
    'bayar', 'bayi', 'beda', 'belajar', 'belanja', 'beli', 'benar', 'bencana', 'benda', 'bentuk', 
    'berat', 'beri', 'besar', 'betul', 'biar', 'biasa', 'bibir', 'bicara', 'bidang', 'biji', 
    'bila', 'bilang', 'bingung', 'bisa', 'bising', 'bisu', 'bohong', 'bola', 'bom', 'buku', 
    'bulan', 'bulu', 'bumi', 'bunga', 'buruk', 'burung', 'butuh', 'cabang', 'cahaya', 'cair', 
    'cakap', 'calon', 'cari', 'catat', 'cegah', 'cepat', 'cerah', 'cerita', 'cetak', 'cicil', 
    'cium', 'coba', 'cuaca', 'cukup', 'cuma', 'dalam', 'damai', 'dapat', 'darah', 'dasar', 
    'datang', 'daun', 'debat', 'dekat', 'delapan', 'dengar', 'dengan', 'depan', 'desa', 'detail', 
    'dewa', 'diary', 'diri', 'doa', 'dosa', 'dua', 'duduk', 'dunia', 'dukung', 'dulu', 
    'empat', 'enak', 'energi', 'enggak', 'entah', 'esok', 'fakta', 'fana', 'fantasi', 'foto', 
    'gabung', 'gaji', 'gambar', 'ganti', 'garis', 'gelap', 'gembira', 'gempa', 'generasi', 'genius', 
    'genting', 'gerak', 'gigi', 'gila', 'gol', 'guling', 'guru', 'habis', 'hadiah', 'hadir', 
    'hafal', 'halaman', 'halu', 'hamba', 'hancur', 'hangat', 'hantu', 'harap', 'harga', 'hari', 
    'harus', 'hati', 'heboh', 'helikopter', 'hemat', 'henti', 'heran', 'hidup', 'hijau', 'hilang', 
    'hitung', 'hormat', 'hubung', 'hujan', 'hukum', 'hutan', 'ia', 'ibadah', 'ibu', 'ide', 
    'ikut', 'ilmu', 'iman', 'indah', 'ingat', 'ingin', 'ini', 'insaf', 'intan', 'istana', 
    'istri', 'itu', 'jaga', 'jalan', 'jangan', 'janji', 'jarang', 'jauh', 'jawab', 'jelek', 
    'jelas', 'jembatan', 'jepang', 'jual', 'juara', 'jujur', 'jumpa', 'juta', 'kabar', 'kaget', 
    'kakak', 'kalah', 'kalau', 'kali', 'kamar', 'kampus', 'kantor', 'kapal', 'karya', 'kata', 
    'kaya', 'kayu', 'keadaan', 'kebal', 'kecil', 'kedinginan', 'kehendak', 'kejam', 'keju', 'kelas', 
    'keluar', 'kemana', 'kembang', 'kembar', 'kena', 'kenal', 'kenangan', 'kencan', 'kencing', 'kepala', 
    'kerja', 'kertas', 'kesehatan', 'ketawa', 'ketua', 'khas', 'kiamat', 'kiri', 'kisah', 'kita', 
    'kiwi', 'koin', 'kokoh', 'kolam', 'komik', 'kongres', 'koran', 'kosong', 'kotor', 'kuat', 
    'kucing', 'kuku', 'kulit', 'kunci', 'kurang', 'laku', 'lalu', 'lama', 'lambat', 'lampu', 
    'langit', 'lanjut', 'laut', 'layar', 'lengan', 'lepas', 'lima', 'lipat', 'logam', 'lompat', 
    'lucu', 'lupa', 'mabuk', 'madu', 'mahal', 'makanan', 'malam', 'malu', 'mampu', 'mana', 
    'mata', 'mawar', 'media', 'meja', 'melodi', 'membaca', 'menang', 'menara', 'mengerti', 'mentah', 
    'merah', 'mesin', 'mimpi', 'minum', 'mobil', 'monyet', 'mulai', 'murah', 'musik', 'naik', 
    'nakal', 'nama', 'nasi', 'negara', 'nenek', 'niat', 'nyaman', 'nyanyi', 'obat', 'olahraga', 
    'omong', 'orang', 'otak', 'pacar', 'pada', 'pagi', 'paham', 'pakaian', 'paling', 'panas', 
    'pandai', 'pangeran', 'pantai', 'papan', 'paru', 'pasir', 'pasti', 'patah', 'paus', 'pedang', 
    'pegang', 'peka', 'pelajaran', 'pelukan', 'pena', 'pensiun', 'penting', 'perang', 'pergi', 'perhiasan', 
    'perlu', 'permisi', 'persis', 'pertama', 'pesan', 'pesta', 'pikir', 'pintar', 'pintu', 'pisang', 
    'pohon', 'pokok', 'polisi', 'pulang', 'punya', 'putih', 'putra', 'radio', 'ragu', 'rahasia', 
    'raja', 'rambut', 'ramping', 'rasa', 'rawat', 'rendah', 'ribut', 'ringan', 'roboh', 'rokok', 
    'ruang', 'rugi', 'rumah', 'rumpun', 'rusak', 'sabar', 'sahabat', 'sakit', 'salah', 'sama', 
    'sampai', 'sampah', 'sandal', 'sangat', 'sapi', 'sarapan', 'satu', 'sawah', 'sayang', 'sayur', 
    'sebab', 'sebelah', 'sebut', 'sedang', 'sedih', 'segala', 'sehat', 'sejarah', 'sejuk', 'sekolah', 
    'selalu', 'selamat', 'selera', 'selesai', 'sembuh', 'sempurna', 'senang', 'seni', 'sentuh', 'sepak', 
    'sepeda', 'seperti', 'seragam', 'serius', 'sering', 'susah', 'syukur', 'tabung', 'tahan', 'tahu', 
    'takut', 'taman', 'tambah', 'tampil', 'tanah', 'tangan', 'tanya', 'tapi', 'tarik', 'tawa', 
    'tebal', 'tegang', 'tegas', 'tekan', 'telinga', 'telur', 'teman', 'tembak', 'tembok', 'tempat', 
    'tenang', 'tenda', 'tentang', 'tepat', 'terang', 'terbang', 'terima', 'terus', 'tetap', 'tidur', 
    'tiga', 'tikus', 'timur', 'tinggi', 'titik', 'tolong', 'tua', 'tulis', 'tunggu', 'uang', 
    'ubur', 'ujung', 'ular', 'umur', 'undang', 'untuk', 'urus', 'usia', 'utama', 'wajah', 
    'waktu', 'wanita', 'warna', 'warta', 'ya', 'yakin', 'yatim', 'zaman', 'zat'
        
        # Provinsi dan kota
        'aceh', 'medan', 'padang', 'palembang', 'lampung', 'bengkulu', 
        'jambi', 'riau', 'pekanbaru', 'batam', 'jakarta', 'bogor',
        'depok', 'tanggerang', 'bekasi', 'bandung', 'jawa barat', 
        'jawa tengah', 'jawa timur', 'yogyakarta', 'surabaya', 'semarang',
        'bali', 'denpasar', 'lombok', 'ntb', 'nusa tenggara', 'kalimantan',
        'borneo', 'sulawesi', 'makassar', 'manado', 'toraja', 'papua',
        'ambon', 'maluku', 'ternate', 'tidore',
        
        # Suku dan budaya
        'jawa', 'sunda', 'batak', 'minang', 'dayak', 'betawi', 'baduy',
        'banjar', 'bugis', 'makassar', 'toraja', 'asmat', 'dani', 'ambon',
        'aceh', 'gayo', 'nias', 'mentawai', 'sasak', 'bima', 'dompu',
        
        # Genre musik
        'dangdut', 'koplo', 'campursari', 'keroncong', 'gamelan', 'jaipong',
        'tarling', 'degung', 'kecapi', 'angklung', 'sasando', 'gambang kromong',
        'tanjidor', 'gondang', 'gandrung', 'joget', 'zapin', 'samrah', 'hadrah',
        'qasidah', 'gambus', 'orkes melayu', 'langgam jawa',
        
        # Penyanyi/band terkenal
        'nike ardilla', 'sheila on 7', 'dmasiv', 'noah', 'peterpan', 'ungu',
        'slank', 'kangen band', 'wali', 'armada', 'setia band', 'geisha',
        'jikustik', 'dewa 19', 'kota', 'kla project', 'bunga citra lestari',
        'agnes mo', 'rossa', 'krisdayanti', 'titi dj', 'ruth sahanaya',
        'andre hehanussa', 'vina panduwinata', 'betharia sonata', 'iwan fals',
        'gombloh', 'ebiet g ade', 'chrisye', 'didi kempot', 'suzanna',
        'alm. rhoma irama', 'soneta group', 'mansyur s', 'meggy z',
        'ita purnamasari', 'viera',

        # Tambahan lainnya
        'nidji', 'letto', 'seventeen', 'lyla', 'ada band', 'five minutes',
        'last child', 'anji', 'glen fredly', 'mahalini', 'tiara andini',
        'judika', 'ariel noah', 'afgan', 'rizky febian', 'tulus', 'yura yunita',
        'marion jola', 'via vallen', 'nella kharisma', 'happy asmara',
        'nissa sabyan', 'sabyan gambus', 'dangdut koplo', 'denny caknan',
        'trio macan', 'tasya rosmala', 'erlando', 'bebi romeo',
        'melly goeslaw', 'republic', 'drive', 'element', 'the rain',
        'kotak', 'cokelat', 'sheila majid', 'gita gutawa', 'delon', 'mellyana manuhutu',
        'yovie widiyanto', 'yovie & nuno', 'the overtunes', 'rafly', 'samsons'
            
        # Lagu daerah
        'bubuy bulan', 'manuk dadali', 'es lilin', 'tokecang', 'soleram',
        'ampar ampar pisang', 'gundul pacul', 'suwe ora jamu', 'gambang suling',
        'jali-jali', 'kicir-kicir', 'lenong', 'ondel-ondel', 'kroncong moritsko',
        
        # Nama khas Indonesia
        'wayang', 'batik', 'borobudur', 'prambanan', 'bali', 'komodo',
        'rendang', 'sate', 'nasi goreng', 'gado-gado', 'keris', 'kujang',
        
        # Pola nama orang Indonesia
        r'(^|\s)(wan|wati|sari|putri|putra|jaya|adi|surya|wijaya|tanjung)',
        r'(siregar|nasution|sinaga|harahap|ginting|sitepu|manik|nainggolan)',
        r'(pane|marpaung|hutagalung|pasaribu|simbolon|sihombing|panggabean)',
        r'(nadeak|sitorus|butar-butar|sembiring|tarigan|perangin-angin)',
        r'(silalahi|tamba|hutapea|pangaribuan|tarihoran|pangihutan)',
        r'(halim|wibowo|gunawan|kusuma|setiawan|santoso|wijaya|yulianto)']

    for track in tracks:
        try:
            # 1. Cek duplikasi
            if check_duplicate_song(track['title'], track['artist']):
                duplicates += 1
                logger.info(f"⏩ Lagu duplikat dilewati: {track['title']} - {track['artist']}")
                continue

            # 2. Deteksi genre Indonesia
            genre = 'international'
            title_check = track['title'].lower()
            artist_check = track['artist'].lower()
            combined_check = f"{title_check} {artist_check}"
            
            # Cek berbagai pola
            if (any(keyword in title_check for keyword in indonesian_keywords) or
                any(keyword in artist_check for keyword in indonesian_keywords) or
                any(keyword in combined_check for keyword in indonesian_keywords) or
                re.search(r'(^|\s)(wan|wati|sari|putri|putra|jaya|adi|surya)($|\s)', artist_check) or
                re.search(r'(siregar|nasution|sinaga|harahap|ginting|sitepu|manik)', artist_check)):
                
                genre = 'indonesian'
                indonesian_detected += 1
                logger.info(f"🇮🇩 Detected Indonesian song: {track['title']} - {track['artist']}")

            # 3. Cari di YouTube
            search_query = f"{track['title']} {track['artist']} official audio"
            youtube_url = search_youtube(search_query)
            
            if not youtube_url:
                error_msg = f"🔍 Tidak ditemukan di YouTube: {track['title']} - {track['artist']}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            deskripsi = f"Album: {track['album']} | From Spotify Playlist | Genre: {genre}"
            
            # 4. Download dengan info genre
            result, error = download_from_youtube(
                youtube_url,
                track['title'],
                track['artist'],
                deskripsi,
                track.get('cover_url'),
                genre=genre
            )
            
            if error:
                logger.warning(f"⚠️ Gagal unduh {track['title']} - {track['artist']}: {error}")
                errors.append(f"{track['title']} - {track['artist']}: {error}")
            else:
                results.append(result)
                
        except Exception as e:
            logger.error(f"❌ Error pada {track['title']} - {track['artist']}: {e}")
            errors.append(f"{track['title']} - {track['artist']}: {str(e)}")
    
    return {
        'success': True,
        'message': f"✅ Playlist selesai. Berhasil: {len(results)}, Gagal: {len(errors)}, Duplikat: {duplicates}, Indonesia: {indonesian_detected}",
        'downloaded': results,
        'errors': errors,
        'stats': {
            'total': len(tracks),
            'success': len(results),
            'failed': len(errors),
            'duplicates': duplicates,
            'indonesian': indonesian_detected
        }
    }, None

def process_youtube_playlist(playlist_url):
    """Proses playlist YouTube dengan deteksi genre dan cek duplikasi"""
    videos = get_youtube_playlist_videos(playlist_url)
    if not videos:
        return None, "❌ Gagal mendapatkan video dari playlist YouTube"
    
    results = []
    errors = []
    duplicates = 0
    indonesian_detected = 0
    
    # Gunakan keyword yang sama seperti Spotify
    indonesian_keywords = [
        # Negara dan umum
        'indonesia', 'indo', 'nusantara', 'tanah air', 'ibu pertiwi',

        # Kata Baku (Formal)
    'abjad', 'absorpsi', 'adab', 'adhesi', 'adibusana', 'adidaya', 'afdal', 'aktif', 'aktivitas',
    'analisis', 'andal', 'antre', 'apotek', 'asas', 'atlet', 'autentik', 'azan', 'balig',
    'batalion', 'baterai', 'bazar', 'bengkel', 'beranda', 'berita', 'bioskop', 'busana', 
    'cendekia', 'cermat', 'cerpen', 'daftar', 'definisi', 'demokrasi', 'diagnosis', 'editor',
    'efektif', 'efisien', 'ekonomi', 'ekosistem', 'elastis', 'elektronika', 'evaluasi', 'faktor',
    'fasilitas', 'filosofi', 'formal', 'fotografi', 'galeri', 'gizi', 'globalisasi', 'grafik',
    'hakikat', 'harmoni', 'hemat', 'hipotesis', 'identitas', 'ideologi', 'ilustrasi', 
    'imajinasi', 'implementasi', 'indikator', 'inovasi', 'inspirasi', 'integritas', 'interaksi',
    'investasi', 'jadwal', 'jurnal', 'kader', 'kreativitas', 'kualitas', 'kuantitas', 'laba',
    'laboratorium', 'legitimasi', 'literasi', 'logika', 'manajemen', 'manipulasi', 'metafora',
    'metodologi', 'motivasi', 'narasi', 'negosiasi', 'objektif', 'observasi', 'optimasi',
    'organisasi', 'paradigma', 'partisipasi', 'penalaran', 'pendidikan', 'pengaruh', 'persepsi',
    'prioritas', 'proaktif', 'progresif', 'prosedur', 'rasional', 'realisasi', 'reformasi',
    'regulasi', 'relevansi', 'resolusi', 'responsif', 'risiko', 'sanksi', 'sarana', 'sastra',
    'sistematis', 'solusi', 'strategi', 'struktur', 'subjektif', 'sukses', 'sumber daya',
    'suplemen', 'sustainabilitas', 'teknologi', 'terintegrasi', 'transparansi', 'tuntas',
    'validasi', 'variabel', 'verifikasi', 'visi', 'vitalitas', 'wacana', 'wawasan', 'wilayah',
    'yuridis', 'zona',

    # Kata Tidak Baku/Slang
    'abis', 'aja', 'ampe', 'banget', 'bencong', 'bokap', 'bonyok', 'cewek', 'cowok', 'dong', 
    'gak', 'gitu', 'gue', 'jomblo', 'kamu', 'kek', 'laper', 'lebay', 'loe', 'mager', 'makan', 
    'mantul', 'ngebut', 'nongkrong', 'nyokap', 'pake', 'parah', 'pede', 'pelit', 'pengen', 
    'resek', 'santai', 'selo', 'seru', 'sok', 'syantik', 'tajir', 'telat', 'temen', 'terus', 
    'udah', 'woles', 'yaudah', 'yoi', 'asek', 'asoy', 'baper', 'bau tanah', 'berisik', 
    'biang kerok', 'capek', 'caper', 'cie', 'cupu', 'cuy', 'demen', 'doyan', 'duduk perkara', 
    'dugem', 'edan', 'emang', 'enak aja', 'galau', 'gaul', 'gengsi', 'gokil', 'gue banget', 
    'hangat-hangat tahi ayam', 'ikrib', 'ilfeel', 'jadul', 'jamet', 'jayus', 'kepo', 'kudet', 
    'lebay', 'lo', 'lucu', 'mantan', 'melas', 'modis', 'muda-mudi', 'ngab', 'ngaret', 'ngedate', 
    'ngeri', 'ngopi', 'ngotot', 'ngegas', 'nyantai', 'nyebelin', 'panik', 'pecicilan', 'pelakor', 
    'penasaran', 'pinter', 'rame', 'receh', 'rempong', 'rileks', 'salah tingkah', 'sangar', 
    'sensi', 'sepik', 'sirik', 'sombong', 'sudah', 'suka-suka', 'syok', 'tampang', 'tengil', 
    'terlalu', 'terpesona', 'tukang gosip', 'wibu', 'yang penting hepi', 'zoomer',

    # Tambahan Kosakata Umum
    'abadi', 'acara', 'adil', 'agama', 'air', 'ajaib', 'akal', 'akar', 'akhirat', 'alam', 
    'alasan', 'alat', 'aliran', 'allah', 'aman', 'anak', 'angin', 'angkat', 'antara', 'api', 
    'arah', 'artikel', 'arus', 'asal', 'asam', 'asap', 'asing', 'awan', 'awal', 'ayah', 
    'badan', 'bagus', 'bahagia', 'bahasa', 'bahan', 'bahaya', 'baik', 'baju', 'bakti', 'balik', 
    'ban', 'bangsa', 'bantah', 'barang', 'baru', 'basah', 'batas', 'batu', 'bau', 'bawa', 
    'bayar', 'bayi', 'beda', 'belajar', 'belanja', 'beli', 'benar', 'bencana', 'benda', 'bentuk', 
    'berat', 'beri', 'besar', 'betul', 'biar', 'biasa', 'bibir', 'bicara', 'bidang', 'biji', 
    'bila', 'bilang', 'bingung', 'bisa', 'bising', 'bisu', 'bohong', 'bola', 'bom', 'buku', 
    'bulan', 'bulu', 'bumi', 'bunga', 'buruk', 'burung', 'butuh', 'cabang', 'cahaya', 'cair', 
    'cakap', 'calon', 'cari', 'catat', 'cegah', 'cepat', 'cerah', 'cerita', 'cetak', 'cicil', 
    'cium', 'coba', 'cuaca', 'cukup', 'cuma', 'dalam', 'damai', 'dapat', 'darah', 'dasar', 
    'datang', 'daun', 'debat', 'dekat', 'delapan', 'dengar', 'dengan', 'depan', 'desa', 'detail', 
    'dewa', 'diary', 'diri', 'doa', 'dosa', 'dua', 'duduk', 'dunia', 'dukung', 'dulu', 
    'empat', 'enak', 'energi', 'enggak', 'entah', 'esok', 'fakta', 'fana', 'fantasi', 'foto', 
    'gabung', 'gaji', 'gambar', 'ganti', 'garis', 'gelap', 'gembira', 'gempa', 'generasi', 'genius', 
    'genting', 'gerak', 'gigi', 'gila', 'gol', 'guling', 'guru', 'habis', 'hadiah', 'hadir', 
    'hafal', 'halaman', 'halu', 'hamba', 'hancur', 'hangat', 'hantu', 'harap', 'harga', 'hari', 
    'harus', 'hati', 'heboh', 'helikopter', 'hemat', 'henti', 'heran', 'hidup', 'hijau', 'hilang', 
    'hitung', 'hormat', 'hubung', 'hujan', 'hukum', 'hutan', 'ia', 'ibadah', 'ibu', 'ide', 
    'ikut', 'ilmu', 'iman', 'indah', 'ingat', 'ingin', 'ini', 'insaf', 'intan', 'istana', 
    'istri', 'itu', 'jaga', 'jalan', 'jangan', 'janji', 'jarang', 'jauh', 'jawab', 'jelek', 
    'jelas', 'jembatan', 'jepang', 'jual', 'juara', 'jujur', 'jumpa', 'juta', 'kabar', 'kaget', 
    'kakak', 'kalah', 'kalau', 'kali', 'kamar', 'kampus', 'kantor', 'kapal', 'karya', 'kata', 
    'kaya', 'kayu', 'keadaan', 'kebal', 'kecil', 'kedinginan', 'kehendak', 'kejam', 'keju', 'kelas', 
    'keluar', 'kemana', 'kembang', 'kembar', 'kena', 'kenal', 'kenangan', 'kencan', 'kencing', 'kepala', 
    'kerja', 'kertas', 'kesehatan', 'ketawa', 'ketua', 'khas', 'kiamat', 'kiri', 'kisah', 'kita', 
    'kiwi', 'koin', 'kokoh', 'kolam', 'komik', 'kongres', 'koran', 'kosong', 'kotor', 'kuat', 
    'kucing', 'kuku', 'kulit', 'kunci', 'kurang', 'laku', 'lalu', 'lama', 'lambat', 'lampu', 
    'langit', 'lanjut', 'laut', 'layar', 'lengan', 'lepas', 'lima', 'lipat', 'logam', 'lompat', 
    'lucu', 'lupa', 'mabuk', 'madu', 'mahal', 'makanan', 'malam', 'malu', 'mampu', 'mana', 
    'mata', 'mawar', 'media', 'meja', 'melodi', 'membaca', 'menang', 'menara', 'mengerti', 'mentah', 
    'merah', 'mesin', 'mimpi', 'minum', 'mobil', 'monyet', 'mulai', 'murah', 'musik', 'naik', 
    'nakal', 'nama', 'nasi', 'negara', 'nenek', 'niat', 'nyaman', 'nyanyi', 'obat', 'olahraga', 
    'omong', 'orang', 'otak', 'pacar', 'pada', 'pagi', 'paham', 'pakaian', 'paling', 'panas', 
    'pandai', 'pangeran', 'pantai', 'papan', 'paru', 'pasir', 'pasti', 'patah', 'paus', 'pedang', 
    'pegang', 'peka', 'pelajaran', 'pelukan', 'pena', 'pensiun', 'penting', 'perang', 'pergi', 'perhiasan', 
    'perlu', 'permisi', 'persis', 'pertama', 'pesan', 'pesta', 'pikir', 'pintar', 'pintu', 'pisang', 
    'pohon', 'pokok', 'polisi', 'pulang', 'punya', 'putih', 'putra', 'radio', 'ragu', 'rahasia', 
    'raja', 'rambut', 'ramping', 'rasa', 'rawat', 'rendah', 'ribut', 'ringan', 'roboh', 'rokok', 
    'ruang', 'rugi', 'rumah', 'rumpun', 'rusak', 'sabar', 'sahabat', 'sakit', 'salah', 'sama', 
    'sampai', 'sampah', 'sandal', 'sangat', 'sapi', 'sarapan', 'satu', 'sawah', 'sayang', 'sayur', 
    'sebab', 'sebelah', 'sebut', 'sedang', 'sedih', 'segala', 'sehat', 'sejarah', 'sejuk', 'sekolah', 
    'selalu', 'selamat', 'selera', 'selesai', 'sembuh', 'sempurna', 'senang', 'seni', 'sentuh', 'sepak', 
    'sepeda', 'seperti', 'seragam', 'serius', 'sering', 'susah', 'syukur', 'tabung', 'tahan', 'tahu', 
    'takut', 'taman', 'tambah', 'tampil', 'tanah', 'tangan', 'tanya', 'tapi', 'tarik', 'tawa', 
    'tebal', 'tegang', 'tegas', 'tekan', 'telinga', 'telur', 'teman', 'tembak', 'tembok', 'tempat', 
    'tenang', 'tenda', 'tentang', 'tepat', 'terang', 'terbang', 'terima', 'terus', 'tetap', 'tidur', 
    'tiga', 'tikus', 'timur', 'tinggi', 'titik', 'tolong', 'tua', 'tulis', 'tunggu', 'uang', 
    'ubur', 'ujung', 'ular', 'umur', 'undang', 'untuk', 'urus', 'usia', 'utama', 'wajah', 
    'waktu', 'wanita', 'warna', 'warta', 'ya', 'yakin', 'yatim', 'zaman', 'zat'
        
        # Provinsi dan kota
        'aceh', 'medan', 'padang', 'palembang', 'lampung', 'bengkulu', 
        'jambi', 'riau', 'pekanbaru', 'batam', 'jakarta', 'bogor',
        'depok', 'tanggerang', 'bekasi', 'bandung', 'jawa barat', 
        'jawa tengah', 'jawa timur', 'yogyakarta', 'surabaya', 'semarang',
        'bali', 'denpasar', 'lombok', 'ntb', 'nusa tenggara', 'kalimantan',
        'borneo', 'sulawesi', 'makassar', 'manado', 'toraja', 'papua',
        'ambon', 'maluku', 'ternate', 'tidore',
        
        # Suku dan budaya
        'jawa', 'sunda', 'batak', 'minang', 'dayak', 'betawi', 'baduy',
        'banjar', 'bugis', 'makassar', 'toraja', 'asmat', 'dani', 'ambon',
        'aceh', 'gayo', 'nias', 'mentawai', 'sasak', 'bima', 'dompu',
        
        # Genre musik
        'dangdut', 'koplo', 'campursari', 'keroncong', 'gamelan', 'jaipong',
        'tarling', 'degung', 'kecapi', 'angklung', 'sasando', 'gambang kromong',
        'tanjidor', 'gondang', 'gandrung', 'joget', 'zapin', 'samrah', 'hadrah',
        'qasidah', 'gambus', 'orkes melayu', 'langgam jawa',
        
        # Penyanyi/band terkenal
        'nike ardilla', 'sheila on 7', 'dmasiv', 'noah', 'peterpan', 'ungu',
        'slank', 'kangen band', 'wali', 'armada', 'setia band', 'geisha',
        'jikustik', 'dewa 19', 'kota', 'kla project', 'bunga citra lestari',
        'agnes mo', 'rossa', 'krisdayanti', 'titi dj', 'ruth sahanaya',
        'andre hehanussa', 'vina panduwinata', 'betharia sonata', 'iwan fals',
        'gombloh', 'ebiet g ade', 'chrisye', 'didi kempot', 'suzanna',
        'alm. rhoma irama', 'soneta group', 'mansyur s', 'meggy z',
        'ita purnamasari', 'viera',

        # Tambahan lainnya
        'nidji', 'letto', 'seventeen', 'lyla', 'ada band', 'five minutes',
        'last child', 'anji', 'glen fredly', 'mahalini', 'tiara andini',
        'judika', 'ariel noah', 'afgan', 'rizky febian', 'tulus', 'yura yunita',
        'marion jola', 'via vallen', 'nella kharisma', 'happy asmara',
        'nissa sabyan', 'sabyan gambus', 'dangdut koplo', 'denny caknan',
        'trio macan', 'tasya rosmala', 'erlando', 'bebi romeo',
        'melly goeslaw', 'republic', 'drive', 'element', 'the rain',
        'kotak', 'cokelat', 'sheila majid', 'gita gutawa', 'delon', 'mellyana manuhutu',
        'yovie widiyanto', 'yovie & nuno', 'the overtunes', 'rafly', 'samsons'
            
        # Lagu daerah
        'bubuy bulan', 'manuk dadali', 'es lilin', 'tokecang', 'soleram',
        'ampar ampar pisang', 'gundul pacul', 'suwe ora jamu', 'gambang suling',
        'jali-jali', 'kicir-kicir', 'lenong', 'ondel-ondel', 'kroncong moritsko',
        
        # Nama khas Indonesia
        'wayang', 'batik', 'borobudur', 'prambanan', 'bali', 'komodo',
        'rendang', 'sate', 'nasi goreng', 'gado-gado', 'keris', 'kujang',
        
        # Pola nama orang Indonesia
        r'(^|\s)(wan|wati|sari|putri|putra|jaya|adi|surya|wijaya|tanjung)',
        r'(siregar|nasution|sinaga|harahap|ginting|sitepu|manik|nainggolan)',
        r'(pane|marpaung|hutagalung|pasaribu|simbolon|sihombing|panggabean)',
        r'(nadeak|sitorus|butar-butar|sembiring|tarigan|perangin-angin)',
        r'(silalahi|tamba|hutapea|pangaribuan|tarihoran|pangihutan)',
        r'(halim|wibowo|gunawan|kusuma|setiawan|santoso|wijaya|yulianto)']  # Sama seperti di atas

    for video in videos:
        try:
            # 1. Ambil metadata untuk cek duplikasi dan deteksi genre
            metadata = get_youtube_metadata_cached(video['url'])
            if not metadata:
                errors.append(f"❌ Gagal dapat metadata: {video['title']}")
                continue

            # 2. Cek duplikasi
            if check_duplicate_song(metadata['judul'], metadata['artis']):
                duplicates += 1
                continue

            # 3. Deteksi genre
            genre = 'international'
            title_check = metadata['judul'].lower()
            artist_check = metadata['artis'].lower()
            combined_check = f"{title_check} {artist_check}"
            
            if (any(keyword in title_check for keyword in indonesian_keywords) or
                any(keyword in artist_check for keyword in indonesian_keywords) or
                any(keyword in combined_check for keyword in indonesian_keywords) or
                re.search(r'(^|\s)(wan|wati|sari|putri|putra)($|\s)', artist_check)):
                
                genre = 'indonesian'
                indonesian_detected += 1

            # 4. Download dengan info genre
            result, error = download_from_youtube(
                video['url'],
                metadata['judul'],
                metadata['artis'],
                metadata.get('deskripsi', ''),
                metadata.get('thumbnail_url'),
                genre=genre
            )
            
            if error:
                logger.warning(f"⚠️ Gagal unduh {video['title']}: {error}")
                errors.append(f"{video['title']}: {error}")
            else:
                results.append(result)
                
        except Exception as e:
            logger.error(f"❌ Error saat memproses {video['title']}: {e}")
            errors.append(f"{video['title']}: {str(e)}")
    
    return {
        'success': True,
        'message': f"✅ Playlist selesai. Berhasil: {len(results)}, Gagal: {len(errors)}, Duplikat: {duplicates}, Indonesia: {indonesian_detected}",
        'downloaded': results,
        'errors': errors,
        'stats': {
            'total': len(videos),
            'success': len(results),
            'failed': len(errors),
            'duplicates': duplicates,
            'indonesian': indonesian_detected
        }
    }, None

def process_youtube_music_playlist(playlist_url):
    """Proses playlist YouTube Music (ditangani seperti playlist YouTube biasa)"""
    return process_youtube_playlist(playlist_url)

# Halaman utama
@app.route('/')
def index():
    user_agent = request.headers.get('User-Agent')

    # Generate UUID
    unique_id = str(uuid.uuid4())

    # Deteksi device dan redirect dengan ID di URL
    if "Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent:
        return redirect(f"/mobile?uuid={unique_id}")
    else:
        return redirect(f"/desktop?uuid={unique_id}")
    
@app.route('/mobile')
def mobile_page():
    return send_from_directory('public', 'mobile.html')

@app.route('/desktop')
def desktop_page():
    return send_from_directory('public', 'desktop.html')

@app.route('/privacy')
def privacy():
    try:
        return send_from_directory('public', 'privacy.html')
    except FileNotFoundError:
        return "Halaman utama sedang dalam pengembangan", 404

@app.route('/terms')
def terms():
    try:
        return send_from_directory('public', 'terms.html')
    except FileNotFoundError:
        return "Halaman utama sedang dalam pengembangan", 404
        
@app.route('/my-account')
def my_account():
    if 'user' not in session:
        return redirect('/login')  # Atau arahkan ke halaman utama
    return render_template('my-account.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js')

# Halaman admin
@app.route('/admin')
def admin_page():
    return send_from_directory('public', 'admin.html')
#Halaman untuk tambah lagu
@app.route('/tambah-lagu')
def tambah_lagu_page():
    return send_from_directory('public', 'tambah-lagu.html')
#Halaman untuk search
@app.route('/search')
def search_lagu_page():
    return send_from_directory('public', 'search.html')
#Halaman untuk register
@app.route('/register', methods=['GET'])
def show_register_page():
    return app.send_static_file('register.html')
#Halaman untuk login
@app.route('/login', methods=['GET'])
def show_login_page():
    return app.send_static_file('login.html')

@app.route('/logout')
def logout_redirect():
    session.clear()
    return redirect('/')

# Route untuk generate URL dengan ID acak
import os
from flask import render_template_string, make_response

@app.route('/stream/audio/<encoded>')
def stream_audio(encoded):
    try:
        decoded_path = decode_path(encoded)
        full_path = os.path.join('data/audio', os.path.basename(decoded_path))
        if not os.path.exists(full_path):
            return "Audio tidak ditemukan", 404
        return send_file(full_path, mimetype='audio/mpeg')
    except Exception as e:
        return f"Error: {e}", 400
    
@app.route('/stream/<encoded>')
def stream_thumb(encoded):
    try:
        decoded_path = decode_path(encoded)
        full_path = os.path.join('public/thumbs', os.path.basename(decoded_path))
        if not os.path.exists(full_path):
            full_path = os.path.join('public/thumbs', 'default.jpg')
        return send_file(full_path, mimetype='image/jpeg')
    except Exception as e:
        return f"Error: {e}", 400
        
@app.route('/play/<random_id>')
def play(random_id):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. Get current track
            cursor.execute("""
                SELECT id, judul as title, artis as artist, 
                       nama_file_audio as audio, thumbnail, random_id
                FROM lagu WHERE random_id = %s
            """, (random_id,))
            current_track = cursor.fetchone()

            if not current_track:
                return "Lagu tidak ditemukan", 404

            # 2. Validate files exist
            audio_path = os.path.join("data/audio", current_track['audio'])
            thumbnail_path = os.path.join("public/thumbs", current_track['thumbnail'])
            
            if not os.path.exists(audio_path):
                return "File audio tidak ditemukan", 404
            
            # Fallback untuk thumbnail jika tidak ada
            if not os.path.exists(thumbnail_path):
                current_track['thumbnail'] = 'default.jpg'

            # 3. Get full playlist
            cursor.execute("""
                SELECT 
                    id, judul as title, artis as artist, 
                    CONCAT('/data/audio/', nama_file_audio) as audio_url,
                    CONCAT('/public/thumbs/', IFNULL(thumbnail, 'default.jpg')) as image,
                    random_id
                FROM lagu 
                ORDER BY tanggal_upload DESC
            """)
            playlist = cursor.fetchall()

            # 4. Find current index
            current_index = next((i for i, t in enumerate(playlist) if t['random_id'] == random_id), 0)

        # 5. Baca template dari folder public
        template_path = os.path.join('public', 'play.html')
        if not os.path.exists(template_path):
            return "Template tidak ditemukan di folder public", 500
            
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 6. Render template dengan data
            rendered_html = template_content
            replacements = {
                '{{ current_track_title }}': current_track['title'],
                '{{ current_track_artist }}': current_track['artist'],
                '{{ current_track_audio_url }}': f"/stream/audio/{encode_path(current_track['audio'])}",
                '{{ current_track_thumbnail }}': f"/stream/{encode_path(current_track['thumbnail'])}",
                '{{ playlist | tojson }}': json.dumps([
                    {
                        **track,
                        "audio_url": f"/stream/audio/{encode_path(track['audio_url'].replace('/data/audio/', ''))}",
                        "image": f"/stream/{encode_path(track['image'].replace('/public/thumbs/', ''))}"
                    } for track in playlist
                ]),
                '{{ current_index }}': str(current_index)
                }


        for placeholder, value in replacements.items():
            rendered_html = rendered_html.replace(placeholder, value)

        response = make_response(rendered_html)
        response.headers['Content-Type'] = 'text/html'
        return response

    except Exception as e:
        app.logger.error(f"Error in /play/{random_id}: {str(e)}")
        return "Terjadi kesalahan server", 500
    finally:
        if conn:
            conn.close()

# Route untuk generate ID acak dan redirect ke URL play
@app.route('/generate')
def generate():
    random_id = generate_random_string(8)  # Panjang ID bisa disesuaikan
    return redirect(url_for('play', random_id=random_id))
'''
# Endpoint untuk file audio
@app.route('/data/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory('data/audio', filename)
'''
from flask import send_from_directory

@app.route('/public/<path:filename>')
def serve_public(filename):
    return send_from_directory('public', filename)

@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('data', filename)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

#Endpoint untuk logo
@app.route('/logo')
def logo():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'logo2.png',
        mimetype='image/png'
    )

#Endpoint untuk icon
@app.route('/icon1')
def icon1():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'icon_192x192.png',
        mimetype='image/png'
    )

@app.route('/icon2')
def icon2():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'icon_512x512.png',
        mimetype='image/png'
    )

@app.route('/sc1')
def sc1():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'screenshot-mobile.png',
        mimetype='image/png'
    )

@app.route('/sc2')
def sc2():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'screenshot-desktop.png',
        mimetype='image/png'
    )

#Endpint untuk playlist
@app.route('/api/playlists', methods=['GET', 'POST'])
def manage_playlists():
    if request.method == 'GET':
        # Dapatkan semua playlist user
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                    SELECT p.id, p.name, p.description, p.created_at,
                           COUNT(ps.song_id) as song_count,
                           u.username as owner
                    FROM playlists p
                    LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
                    LEFT JOIN users u ON p.user_id = u.id
                    WHERE p.user_id = %s OR p.is_public = 1
                    GROUP BY p.id
                    ORDER BY p.created_at DESC
                """, (session['user_id'],))
                
                playlists = cursor.fetchall()
                
                # Format tanggal
                for p in playlists:
                    p['created_at'] = p['created_at'].strftime('%Y-%m-%d %H:%M')
                    p['song_count'] = int(p['song_count'] or 0)
                    
                return jsonify(playlists)
                
        except Exception as e:
            logger.error(f"Get playlists error: {e}")
            return jsonify({'error': 'Gagal mengambil playlist'}), 500
        finally:
            if conn:
                conn.close()
                
    elif request.method == 'POST':
        # Buat playlist baru
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'error': 'Nama playlist diperlukan'}), 400
            
        name = data['name']
        description = data.get('description', '')
        is_public = data.get('is_public', False)
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO playlists
                    (user_id, name, description, is_public, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (session['user_id'], name, description, is_public))
                playlist_id = cursor.lastrowid
                conn.commit()
                
                return jsonify({
                    'id': playlist_id,
                    'name': name,
                    'message': 'Playlist berhasil dibuat'
                }), 201
                
        except Exception as e:
            logger.error(f"Create playlist error: {e}")
            return jsonify({'error': 'Gagal membuat playlist'}), 500
        finally:
            if conn:
                conn.close()

@app.route('/api/playlists/<int:playlist_id>', methods=['GET', 'PUT', 'DELETE'])
def playlist_detail(playlist_id):
    if request.method == 'GET':
        # Dapatkan detail playlist beserta lagunya
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Dapatkan info playlist
                cursor.execute("""
                    SELECT p.*, u.username as owner
                    FROM playlists p
                    JOIN users u ON p.user_id = u.id
                    WHERE p.id = %s AND (p.user_id = %s OR p.is_public = 1)
                """, (playlist_id, session.get('user_id', -1)))
                playlist = cursor.fetchone()
                
                if not playlist:
                    return jsonify({'error': 'Playlist tidak ditemukan'}), 404
                    
                # Dapatkan lagu dalam playlist
                cursor.execute("""
                    SELECT l.id, l.judul as title, l.artis as artist,
                           l.duration, l.thumbnail, l.random_id
                    FROM lagu l
                    JOIN playlist_songs ps ON l.id = ps.song_id
                    WHERE ps.playlist_id = %s
                    ORDER BY ps.position
                """, (playlist_id,))
                songs = cursor.fetchall()
                
                # Format response
                playlist['created_at'] = playlist['created_at'].strftime('%Y-%m-%d %H:%M')
                playlist['songs'] = songs
                
                return jsonify(playlist)
                
        except Exception as e:
            logger.error(f"Get playlist error: {e}")
            return jsonify({'error': 'Gagal mengambil detail playlist'}), 500
        finally:
            if conn:
                conn.close()
                
    elif request.method == 'PUT':
        # Update playlist
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Data tidak valid'}), 400
            
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Verifikasi kepemilikan playlist
                cursor.execute("""
                    SELECT user_id FROM playlists WHERE id = %s
                """, (playlist_id,))
                owner = cursor.fetchone()
                
                if not owner or owner['user_id'] != session['user_id']:
                    return jsonify({'error': 'Anda tidak memiliki akses ke playlist ini'}), 403
                    
                # Update data
                updates = []
                values = []
                
                if 'name' in data:
                    updates.append("name = %s")
                    values.append(data['name'])
                if 'description' in data:
                    updates.append("description = %s")
                    values.append(data.get('description', ''))
                if 'is_public' in data:
                    updates.append("is_public = %s")
                    values.append(data['is_public'])
                    
                if not updates:
                    return jsonify({'error': 'Tidak ada data yang diupdate'}), 400
                    
                values.append(playlist_id)
                
                query = f"""
                    UPDATE playlists
                    SET {', '.join(updates)}
                    WHERE id = %s
                """
                cursor.execute(query, values)
                conn.commit()
                
                return jsonify({'message': 'Playlist berhasil diupdate'}), 200
                
        except Exception as e:
            logger.error(f"Update playlist error: {e}")
            return jsonify({'error': 'Gagal mengupdate playlist'}), 500
        finally:
            if conn:
                conn.close()
                
    elif request.method == 'DELETE':
        # Hapus playlist
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Verifikasi kepemilikan playlist
                cursor.execute("""
                    SELECT user_id FROM playlists WHERE id = %s
                """, (playlist_id,))
                owner = cursor.fetchone()
                
                if not owner or owner['user_id'] != session['user_id']:
                    return jsonify({'error': 'Anda tidak memiliki akses ke playlist ini'}), 403
                    
                # Hapus relasi lagu dulu
                cursor.execute("""
                    DELETE FROM playlist_songs WHERE playlist_id = %s
                """, (playlist_id,))
                
                # Hapus playlist
                cursor.execute("""
                    DELETE FROM playlists WHERE id = %s
                """, (playlist_id,))
                
                conn.commit()
                
                return jsonify({'message': 'Playlist berhasil dihapus'}), 200
                
        except Exception as e:
            logger.error(f"Delete playlist error: {e}")
            return jsonify({'error': 'Gagal menghapus playlist'}), 500
        finally:
            if conn:
                conn.close()

# Route untuk download dan menyimpan lagu
@app.route('/download', methods=['POST'])
def download_song():
    youtube_url = request.json.get('url')
    if not youtube_url:
        return jsonify({'error': 'URL tidak ditemukan'}), 400

    try:
        file_name = download_and_save_song(youtube_url)
        return jsonify({'message': 'Lagu berhasil diunduh dan disimpan', 'file': file_name}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>/songs', methods=['POST', 'GET', 'DELETE'])
def manage_playlist_songs(playlist_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    if not data or 'song_id' not in data:
        return jsonify({'error': 'ID lagu diperlukan'}), 400
        
    song_id = data['song_id']
    
    if request.method == 'POST':
        # Tambahkan lagu ke playlist
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Verifikasi kepemilikan playlist
                cursor.execute("""
                    SELECT user_id FROM playlists WHERE id = %s
                """, (playlist_id,))
                owner = cursor.fetchone()
                
                if not owner or owner['user_id'] != session['user_id']:
                    return jsonify({'error': 'Anda tidak memiliki akses ke playlist ini'}), 403
                    
                # Verifikasi lagu ada
                cursor.execute("""
                    SELECT 1 FROM lagu WHERE id = %s
                """, (song_id,))
                if not cursor.fetchone():
                    return jsonify({'error': 'Lagu tidak ditemukan'}), 404
                    
                # Cek apakah lagu sudah ada di playlist
                cursor.execute("""
                    SELECT 1 FROM playlist_songs 
                    WHERE playlist_id = %s AND song_id = %s
                """, (playlist_id, song_id))
                if cursor.fetchone():
                    return jsonify({'error': 'Lagu sudah ada di playlist ini'}), 409
                    
                # Dapatkan posisi terakhir
                cursor.execute("""
                    SELECT MAX(position) as max_pos 
                    FROM playlist_songs 
                    WHERE playlist_id = %s
                """, (playlist_id,))
                result = cursor.fetchone()
                position = (result['max_pos'] or 0) + 1
                
                # Tambahkan lagu
                cursor.execute("""
                    INSERT INTO playlist_songs
                    (playlist_id, song_id, position, added_at)
                    VALUES (%s, %s, %s, NOW())
                """, (playlist_id, song_id, position))
                conn.commit()
                
                return jsonify({
                    'message': 'Lagu berhasil ditambahkan ke playlist',
                    'position': position
                }), 201
                
        except Exception as e:
            logger.error(f"Add song to playlist error: {e}")
            return jsonify({'error': 'Gagal menambahkan lagu ke playlist'}), 500
        finally:
            if conn:
                conn.close()
                
    elif request.method == 'DELETE':
        # Hapus lagu dari playlist
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Verifikasi kepemilikan playlist
                cursor.execute("""
                    SELECT user_id FROM playlists WHERE id = %s
                """, (playlist_id,))
                owner = cursor.fetchone()
                
                if not owner or owner['user_id'] != session['user_id']:
                    return jsonify({'error': 'Anda tidak memiliki akses ke playlist ini'}), 403
                    
                # Hapus lagu
                cursor.execute("""
                    DELETE FROM playlist_songs
                    WHERE playlist_id = %s AND song_id = %s
                """, (playlist_id, song_id))
                
                # Update posisi lagu yang tersisa
                cursor.execute("""
                    UPDATE playlist_songs ps
                    JOIN (
                        SELECT id, ROW_NUMBER() OVER (ORDER BY position) as new_pos
                        FROM playlist_songs
                        WHERE playlist_id = %s
                    ) as t ON ps.id = t.id
                    SET ps.position = t.new_pos
                    WHERE ps.playlist_id = %s
                """, (playlist_id, playlist_id))
                
                conn.commit()
                
                return jsonify({'message': 'Lagu berhasil dihapus dari playlist'}), 200
                
        except Exception as e:
            logger.error(f"Remove song from playlist error: {e}")
            return jsonify({'error': 'Gagal menghapus lagu dari playlist'}), 500
        finally:
            if conn:
                conn.close()

#Endpoint Histori
@app.route('/api/history', methods=['GET'])
def get_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    limit = request.args.get('limit', default=20, type=int)
    if limit > 100:
        limit = 100
        
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT h.id, h.played_at, 
                       l.id as song_id, l.judul as title, l.artis as artist,
                       l.thumbnail, l.duration, l.random_id
                FROM history h
                JOIN lagu l ON h.song_id = l.id
                WHERE h.user_id = %s
                ORDER BY h.played_at DESC
                LIMIT %s
            """, (session['user_id'], limit))
            
            history = cursor.fetchall()
            
            # Format tanggal
            for item in history:
                item['played_at'] = item['played_at'].strftime('%Y-%m-%d %H:%M')
                
            return jsonify(history)
            
    except Exception as e:
        logger.error(f"Get history error: {e}")
        return jsonify({'error': 'Gagal mengambil riwayat'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/history/recent', methods=['GET'])
def get_recent_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    limit = request.args.get('limit', default=5, type=int)
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT l.id, l.judul as title, l.artis as artist,
                       l.thumbnail, l.duration, l.random_id,
                       MAX(h.played_at) as last_played
                FROM history h
                JOIN lagu l ON h.song_id = l.id
                WHERE h.user_id = %s
                GROUP BY l.id
                ORDER BY last_played DESC
                LIMIT %s
            """, (session['user_id'], limit))
            
            recent = cursor.fetchall()
            
            # Format tanggal
            for item in recent:
                item['last_played'] = item['last_played'].strftime('%Y-%m-%d %H:%M')
                
            return jsonify(recent)
            
    except Exception as e:
        logger.error(f"Get recent history error: {e}")
        return jsonify({'error': 'Gagal mengambil riwayat terakhir'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/history/add', methods=['POST'])
def add_to_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    if not data or 'song_id' not in data:
        return jsonify({'error': 'ID lagu diperlukan'}), 400
        
    song_id = data['song_id']
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Verifikasi lagu ada
            cursor.execute("""
                SELECT 1 FROM lagu WHERE id = %s
            """, (song_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Lagu tidak ditemukan'}), 404
                
            # Tambahkan ke riwayat
            cursor.execute("""
                INSERT INTO history (user_id, song_id, played_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE played_at = NOW()
            """, (session['user_id'], song_id))
            conn.commit()
            
            return jsonify({'message': 'Riwayat diperbarui'}), 200
            
    except Exception as e:
        logger.error(f"Add to history error: {e}")
        return jsonify({'error': 'Gagal menambahkan ke riwayat'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    if 'user_id' not in session:
        # Untuk pengguna tidak login, berikan rekomendasi umum
        return get_general_recommendations()
        
    limit = request.args.get('limit', default=10, type=int)
    if limit > 20:
        limit = 20
        
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. Dapatkan genre favorit user berdasarkan riwayat
            cursor.execute("""
                SELECT l.genre, COUNT(*) as play_count
                FROM history h
                JOIN lagu l ON h.song_id = l.id
                WHERE h.user_id = %s
                GROUP BY l.genre
                ORDER BY play_count DESC
                LIMIT 3
            """, (session['user_id'],))
            
            top_genres = [row['genre'] for row in cursor.fetchall()]
            
            # 2. Dapatkan artis favorit
            cursor.execute("""
                SELECT l.artis, COUNT(*) as play_count
                FROM history h
                JOIN lagu l ON h.song_id = l.id
                WHERE h.user_id = %s
                GROUP BY l.artis
                ORDER BY play_count DESC
                LIMIT 5
            """, (session['user_id'],))
            
            top_artists = [row['artis'] for row in cursor.fetchall()]
            
            # 3. Generate query rekomendasi
            query_parts = []
            params = []
            
            if top_genres:
                query_parts.append("(genre IN (%s))" % ','.join(['%s']*len(top_genres)))
                params.extend(top_genres)
                
            if top_artists:
                query_parts.append("(artis IN (%s))" % ','.join(['%s']*len(top_artists)))
                params.extend(top_artists)
                
            if not query_parts:
                return get_general_recommendations()
                
            where_clause = " OR ".join(query_parts)
            params.append(limit)
            
            # 4. Dapatkan rekomendasi
            cursor.execute(f"""
                SELECT id, judul as title, artis as artist,
                       thumbnail, duration, random_id
                FROM lagu
                WHERE ({where_clause})
                AND id NOT IN (
                    SELECT song_id FROM history 
                    WHERE user_id = %s
                )
                ORDER BY RAND()
                LIMIT %s
            """, [*params, session['user_id']])
            
            recommendations = cursor.fetchall()
            
            # Jika kurang dari limit, tambahkan rekomendasi umum
            if len(recommendations) < limit:
                cursor.execute("""
                    SELECT id, judul as title, artis as artist,
                           thumbnail, duration, random_id
                    FROM lagu
                    WHERE id NOT IN (
                        SELECT song_id FROM history 
                        WHERE user_id = %s
                    )
                    AND id NOT IN %s
                    ORDER BY RAND()
                    LIMIT %s
                """, (session['user_id'], 
                     tuple(r['id'] for r in recommendations) or (0,),
                     limit - len(recommendations)))
                
                recommendations.extend(cursor.fetchall())
                
            return jsonify(recommendations)
            
    except Exception as e:
        logger.error(f"Get recommendations error: {e}")
        return get_general_recommendations()
    finally:
        if conn:
            conn.close()

def get_general_recommendations(limit=10):
    """Rekomendasi umum untuk pengguna tidak login atau sebagai fallback"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, judul as title, artis as artist,
                       thumbnail, duration, random_id
                FROM lagu
                ORDER BY RAND()
                LIMIT %s
            """, (limit,))
            
            return jsonify(cursor.fetchall())
            
    except Exception as e:
        logger.error(f"Get general recommendations error: {e}")
        return jsonify([])
    finally:
        if conn:
            conn.close()
'''
#Endpoint untuk register
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    required_fields = ['username', 'email', 'password']
    
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    username = data['username']
    email = data['email']
    password = data['password']

    # Validasi input
    if len(username) < 3 or len(username) > 50:
        return jsonify({'error': 'Username must be 3-50 characters'}), 400
    if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
        return jsonify({'error': 'Invalid email format'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    conn = None
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        verification_code = secrets.token_urlsafe(32)
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, verification_code)
                VALUES (%s, %s, %s, %s)
            """, (username, email, hashed, verification_code))
            conn.commit()
        
        # Kirim email verifikasi
        try:
            send_verification_email(email, verification_code)
        except Exception as email_err:
            logger.error(f"Gagal kirim email verifikasi: {email_err}")
            return jsonify({'error': 'Gagal mengirim email verifikasi'}), 500

        return jsonify({'message': 'Registrasi berhasil. Silakan cek email untuk verifikasi.'}), 201
        
    except pymysql.err.IntegrityError as e:
        if 'username' in str(e).lower():
            return jsonify({'error': 'Username already exists'}), 409
        elif 'email' in str(e).lower():
            return jsonify({'error': 'Email already exists'}), 409
        return jsonify({'error': 'Registration failed'}), 500
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        if conn:
            conn.close()

# Complete verification endpoint
@app.route('/api/auth/verify', methods=['GET'])
def verify():
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Verification code required'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users 
                SET is_verified = TRUE, verification_code = NULL 
                WHERE verification_code = %s
            """, (code,))
            if cursor.rowcount == 0:
                return jsonify({'error': 'Invalid verification code'}), 400
            conn.commit()
        
        return jsonify({'message': 'Account verified successfully'}), 200
    except Exception as e:
        logger.error(f"Verification error: {e}")
        return jsonify({'error': 'Verification failed'}), 500
    finally:
        if conn:
            conn.close()

# Complete login endpoint
@app.route('/api/auth/login', methods=['POST'])
def login():
    conn = None
    data = request.get_json()
    if not data or 'email_or_username' not in data or 'password' not in data:
        return jsonify({'error': 'Email/username and password required'}), 400

    email_or_username = data['email_or_username']
    password = data['password']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, email, password_hash, is_verified
                FROM users
                WHERE email = %s OR username = %s
            """, (email_or_username, email_or_username))
            user = cursor.fetchone()

            if not user:
                return jsonify({'error': 'Invalid credentials'}), 401

            if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                return jsonify({'error': 'Invalid credentials'}), 401

            if not user['is_verified']:
                return jsonify({'error': 'Account not verified'}), 403

            cursor.execute("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (user['id'],))
            conn.commit()

            session['user_id'] = user['id']
            session['username'] = user['username']

            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
            }), 200
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500
    finally:
        if conn:
            conn.close()

# Complete logout endpoint
@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200

# Complete authentication status endpoint
@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    if 'user_id' not in session:
        return jsonify({'isLoggedIn': False}), 200

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, email, profile_picture
                FROM users
                WHERE id = %s
            """, (session['user_id'],))
            user = cursor.fetchone()

            if not user:
                session.clear()
                return jsonify({'isLoggedIn': False}), 200

            return jsonify({
                'isLoggedIn': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'profilePicture': user['profile_picture']
                }
            }), 200
    except Exception as e:
        logger.error(f"Auth status error: {e}")
        return jsonify({'isLoggedIn': False}), 200
    finally:
        if conn:
            conn.close()'''

# Ambil daftar lagu dari database
@app.route('/tracks', methods=['GET'])
def get_tracks():
    try:    
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, judul, artis, deskripsi, nama_file_audio, thumbnail, tanggal_upload, random_id
                FROM lagu 
                ORDER BY tanggal_upload DESC
            """)
            lagu_list = cursor.fetchall()
        conn.close()

        result = []
        for row in lagu_list:
            # Jika random_id belum ada, generate dan simpan ke database
            if not row['random_id']:
                random_id = generate_random_string(8)
                conn = pymysql.connect(**DB_CONFIG)
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE lagu SET random_id = %s WHERE id = %s
                    """, (random_id, row['id']))
                    conn.commit()
                conn.close()
                row['random_id'] = random_id  # Update hasil query

            result.append({
                'random_id': row['random_id'],  # Gunakan random_id dari database
                'id': row['id'],
                'name': row['judul'],
                'artist': row['artis'],
                'audio': f"/data/audio/{row['nama_file_audio']}",
                'image': f"/public/thumbs/{row['thumbnail']}",
                'description': row['deskripsi'] or "",
                'upload_date': row['tanggal_upload'].strftime('%Y-%m-%d %H:%M:%S')
            })

        return jsonify(result)
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'Gagal mengambil data lagu'}), 500

# Endpoint untuk upload lagu
@app.route('/admin/upload', methods=['POST'])
def upload_track():
    """Endpoint untuk upload lagu dengan deteksi genre dan cek duplikasi"""
    data = request.get_json()
    if not data:
        return jsonify({
            'error': 'Data tidak valid',
            'detail': 'Request body harus berupa JSON'
        }), 400

    url = data.get('url')
    if not url or not url.startswith('http'):
        return jsonify({
            'error': 'URL tidak valid',
            'detail': 'URL harus dimulai dengan http/https'
        }), 400

    try:
        # 1. Cek metadata dasar sebelum proses
        metadata = None
        if 'spotify.com' in url:
            metadata = get_spotify_metadata_cached(url)
        elif 'youtube.com' in url or 'youtu.be' in url:
            metadata = get_youtube_metadata_cached(url)
        else:
            return jsonify({
                'error': 'Jenis URL tidak didukung',
                'detail': 'Hanya URL YouTube atau Spotify yang didukung',
                'supported_formats': [
                    'YouTube (https://youtube.com/watch?v=...)',
                    'YouTube Shorts (https://youtu.be/...)',
                    'Spotify Track (https://open.spotify.com/track/...)'
                ]
            }), 400

        # 2. Cek duplikasi jika metadata tersedia
        if metadata and metadata.get('judul') and metadata.get('artis'):
            if check_duplicate_song(metadata['judul'], metadata['artis']):
                return jsonify({
                    'error': 'Lagu sudah ada',
                    'code': 'DUPLICATE_SONG',
                    'detail': 'Lagu dengan judul dan artis yang sama sudah ada di database',
                    'metadata': metadata
                }), 409

        # 3. Proses download berdasarkan jenis URL
        result = None
        error = None
        
        if 'spotify.com' in url:
            result, error = download_from_spotify(url)
        else:  # YouTube
            # Gunakan metadata yang sudah diambil untuk efisiensi
            result, error = download_from_youtube(
                url,
                judul=metadata.get('judul') if metadata else None,
                artis=metadata.get('artis') if metadata else None,
                deskripsi=metadata.get('deskripsi') if metadata else None,
                thumbnail_url=metadata.get('thumbnail_url') if metadata else None
            )

        # 4. Handle hasil download
        if error:
            logger.error(f"Upload error: {error}")
            return jsonify({
                'error': 'Gagal mengunggah lagu',
                'detail': error,
                'type': 'UPLOAD_ERROR'
            }), 500

        # Pastikan result memiliki nilai default
        if result:
            result.update({
                'judul': result.get('judul') or 'Judul Tidak Diketahui',
                'artis': result.get('artis') or 'Artis Tidak Diketahui',
                'deskripsi': result.get('deskripsi') or '',
                'genre': result.get('genre') or 'international'
            })

        # 5. Response sukses
        logger.info(f"Upload berhasil dari {url}")
        return jsonify({
            'success': True,
            'message': '✅ Lagu berhasil diunggah',
            'data': result,
            'metadata': metadata,
            'warnings': []  # Untuk pesan warning tambahan
        })

    except Exception as e:
        logger.error(f"Upload exception: {e}", exc_info=True)
        return jsonify({
            'error': 'Terjadi kesalahan saat upload',
            'detail': str(e),
            'type': 'SERVER_ERROR',
            'timestamp': datetime.now().isoformat()
        }), 500
        
@app.route('/admin/get-metadata', methods=['POST'])
def get_metadata():
    """Endpoint untuk mengambil metadata dari URL YouTube atau Spotify"""
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL wajib disertakan'}), 400

    url = data['url']
    metadata = None

    try:
        start_time = time.time()
        logger.info(f"Memulai pengambilan metadata untuk: {url}")

        if 'youtube.com' in url or 'youtu.be' in url:
            try:
                metadata = get_youtube_metadata(url)  # gunakan API YouTube v3
                if not metadata:
                    raise Exception("Gagal mendapatkan metadata YouTube")
            except Exception as e:
                logger.error(f"Error YouTube metadata: {e}")
                return jsonify({
                    'error': 'Gagal mengambil metadata YouTube',
                    'detail': str(e),
                    'type': 'youtube_error'
                }), 500

        elif 'spotify.com' in url:
            if not sp:
                return jsonify({'error': 'Spotify client tidak terinisialisasi'}), 500
            try:
                metadata = get_spotify_metadata_cached(url)
                if not metadata:
                    raise Exception("Gagal mendapatkan metadata Spotify")
            except Exception as e:
                logger.error(f"Error Spotify metadata: {e}")
                return jsonify({
                    'error': 'Gagal mengambil metadata Spotify',
                    'detail': str(e),
                    'type': 'spotify_error'
                }), 500
        else:
            return jsonify({'error': 'Hanya URL YouTube atau Spotify yang didukung'}), 400

        processing_time = time.time() - start_time
        logger.info(f"Metadata berhasil diambil dalam {processing_time:.2f} detik")
        return jsonify({
            'success': True,
            'metadata': metadata,
            'processing_time': f"{processing_time:.2f} detik"
        })

    except Exception as e:
        logger.error(f"Metadata endpoint error: {e}")
        return jsonify({
            'error': 'Terjadi kesalahan saat mengambil metadata',
            'detail': str(e),
            'type': 'general_error'
        }), 500

# Route untuk /admin/download-playlist
@app.route('/admin/download-playlist', methods=['GET'])
def download_playlist_view():
    """Endpoint untuk mengunduh playlist berdasarkan URL"""
    playlist_url = request.args.get('url')  # Mendapatkan URL dari parameter query
    if not playlist_url:
        return jsonify({"message": "❌ URL Playlist tidak ditemukan"}), 400

    logger.info(f"Processing playlist: {playlist_url}")
    
    response, error = download_playlist(playlist_url)
    if error:
        return jsonify({"message": f"❌ {error}"}), 500
    return jsonify({
        "message": f"✅ {response['message']}",
        "downloaded": response.get('downloaded', []),
        "errors": response.get('errors', [])
    }), 200

@app.route('/api/lagu/<int:lagu_id>', methods=['GET', 'PUT', 'DELETE'])
def kelola_lagu(lagu_id):
    koneksi = None
    try:
        koneksi = get_db_connection()
        
        if request.method == 'GET':
            # Ambil detail lagu
            with koneksi.cursor(pymysql.cursors.DictCursor) as kursor:
                kursor.execute("SELECT * FROM lagu WHERE id = %s", (lagu_id,))
                lagu = kursor.fetchone()
                
                if not lagu:
                    return jsonify({'error': 'Lagu tidak ditemukan'}), 404
                    
                return jsonify({
                    'id': lagu['id'],
                    'judul': lagu['judul'],
                    'artis': lagu['artis'],
                    'deskripsi': lagu['deskripsi'],
                    'thumbnail': f"/public/thumbs/{lagu['thumbnail']}",
                    'file_audio': f"/data/audio/{lagu['nama_file_audio']}"
                })
                
        elif request.method == 'PUT':
            # Update data lagu
            data = request.form

            # Cek thumbnail di 'thumbs' atau 'thumbnail'
            file_thumbnail = request.files.get('thumbs') or request.files.get('thumbnail')
            nama_thumbnail = None

            if file_thumbnail and file_thumbnail.filename:
                # Simpan thumbnail baru
                direktori_thumbnail = os.path.join('public', 'thumbs')
                os.makedirs(direktori_thumbnail, exist_ok=True)

                # Buat nama file aman
                nama_asli = secure_filename(file_thumbnail.filename)
                nama_thumbnail = f"{lagu_id}_{nama_asli}"
                path_thumbnail = os.path.join(direktori_thumbnail, nama_thumbnail)

                file_thumbnail.save(path_thumbnail)
            else:
                # Pertahankan thumbnail lama jika tidak diubah
                with koneksi.cursor() as kursor:
                    kursor.execute("SELECT thumbnail FROM lagu WHERE id = %s", (lagu_id,))
                    nama_thumbnail = kursor.fetchone()[0]

            # Update database
            with koneksi.cursor() as kursor:
                kursor.execute(
                    """UPDATE lagu 
                    SET judul = %s, artis = %s, deskripsi = %s, thumbnail = %s 
                    WHERE id = %s""",
                    (data.get('judul'), data.get('artis'), data.get('deskripsi'),
                    nama_thumbnail, lagu_id)
                )
                koneksi.commit()

            return jsonify({'sukses': True, 'pesan': 'Data lagu berhasil diperbarui'})
            
        elif request.method == 'DELETE':
            # Hapus lagu
            with koneksi.cursor() as kursor:
                # Ambil info file untuk dihapus
                kursor.execute(
                    "SELECT nama_file_audio, thumbnail FROM lagu WHERE id = %s", 
                    (lagu_id,))
                hasil = kursor.fetchone()
                
                if not hasil:
                    return jsonify({'error': 'Lagu tidak ditemukan'}), 404
                
                file_audio, file_thumbnail = hasil
                
                # Hapus dari database
                kursor.execute("DELETE FROM lagu WHERE id = %s", (lagu_id,))
                koneksi.commit()
                
                # Hapus file
                try:
                    os.remove(os.path.join('data', 'audio', file_audio))
                    os.remove(os.path.join('public', 'thumbs', file_thumbnail))
                    os.remove(os.path.join('data', 'thumbs', file_thumbnail))
                except OSError as e:
                    logging.warning(f"Gagal menghapus file: {e}")
                    
            return jsonify({'sukses': True, 'pesan': 'Lagu berhasil dihapus'})
            
    except Exception as e:
        logging.error(f"Error database: {e}")
        return jsonify({'error': 'Terjadi kesalahan server'}), 500
    finally:
        if koneksi:
            koneksi.close()

# ======================
# ENDPOINT UTAMA MUSIC PLAYER
# ======================

@app.route('/api/player/songs', methods=['GET'])
def get_all_songs():
    """Endpoint untuk mendapatkan semua lagu dengan random_id"""
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get all public songs
            cursor.execute("""
                SELECT 
                    id, judul as title, artis as artist,
                    nama_file_audio as audio_file, 
                    thumbnail as cover_url,
                    duration, plays, likes,
                    tanggal_upload as upload_date,
                    genre,
                    random_id
                FROM lagu
                WHERE is_public = 1
                ORDER BY tanggal_upload DESC
            """)
            songs = cursor.fetchall()

            # Process results
            result = []
            for song in songs:
                # Generate random_id if missing
                if not song['random_id']:
                    random_id = generate_random_string(8)
                    try:
                        with conn.cursor() as update_cursor:
                            update_cursor.execute("""
                                UPDATE lagu SET random_id = %s 
                                WHERE id = %s
                            """, (random_id, song['id']))
                            conn.commit()
                        song['random_id'] = random_id
                    except Exception as update_err:
                        logger.error(f"Failed to update random_id: {update_err}")
                        continue

                # Format response
                result.append({
                    'id': song['id'],
                    'random_id': song['random_id'],
                    'title': song['title'],
                    'artist': song['artist'],
                    'audio_url': f"/data/audio/{song['audio_file']}",
                    'cover_url': f"/public/thumbs/{song['cover_url']}",
                    'duration': song['duration'] or 0,
                    'plays': song['plays'] or 0,
                    'likes': song['likes'] or 0,
                    'upload_date': song['upload_date'].strftime('%Y-%m-%d'),
                    'genre': song['genre'] or 'Unknown'
                })

            return jsonify(result)

    except Exception as e:
        logger.error(f"Error in /api/player/songs: {str(e)}")
        return jsonify({
            'error': 'Failed to get songs',
            'details': str(e)
        }), 500
    finally:
        if conn:
            conn.close()

#Endpoin untuk recomended
@app.route('/api/player/recommended', methods=['GET'])
def get_recommended_songs():
    """Endpoint untuk mendapatkan lagu rekomendasi"""
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get 12 random songs
            cursor.execute("""
                SELECT 
                    id, judul as title, artis as artist,
                    nama_file_audio as audio_file, 
                    thumbnail as cover_url,
                    duration
                FROM lagu
                WHERE is_public = 1
                ORDER BY RAND()
                LIMIT 12
            """)
            songs = cursor.fetchall()

            # Format response
            result = [{
                'id': song['id'],
                'title': song['title'],
                'artist': song['artist'],
                'audio_url': f"/data/audio/{song['audio_file']}",
                'cover_url': f"/public/thumbs/{song['cover_url']}",
                'duration': song['duration'] or 0
            } for song in songs]

            return jsonify(result)

    except Exception as e:
        logger.error(f"Error in /api/player/recommended: {str(e)}")
        return jsonify({
            'error': 'Failed to get recommended songs',
            'details': str(e)
        }), 500
    finally:
        if conn:
            conn.close()

#Endpoint filter
@app.route('/api/player/songs/indonesian', methods=['GET'])
def get_indonesian_songs():
    """Endpoint untuk lagu Indonesia"""
    return get_filtered_songs(filter_type='indonesian')

@app.route('/api/player/songs/international', methods=['GET'])
def get_international_songs():
    """Endpoint untuk lagu internasional"""
    return get_filtered_songs(filter_type='international')

def get_filtered_songs(filter_type):
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            if filter_type == 'indonesian':
                query = """
                    SELECT * FROM lagu 
                    WHERE (artis LIKE '%indonesia%' OR genre = 'indonesian')
                    AND is_public = 1
                    ORDER BY RAND()
                """
            else:  # international
                query = """
                    SELECT * FROM lagu 
                    WHERE (artis NOT LIKE '%indonesia%' OR genre = 'international')
                    AND is_public = 1
                    ORDER BY RAND()
                """
            
            cursor.execute(query)
            songs = cursor.fetchall()

            result = [{
                'id': song['id'],
                'title': song['judul'],
                'artist': song['artis'],
                'audio_url': f"/data/audio/{song['nama_file_audio']}",
                'cover_url': f"/public/thumbs/{song['thumbnail']}",
                'duration': song['duration'] or 0
            } for song in songs]

            return jsonify(result)

    except Exception as e:
        logger.error(f"Error in filtered songs: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# Helper function untuk generate random string
def generate_random_string(length=8):
    import random
    import string
    return ''.join(random.choices(
        string.ascii_letters + string.digits, 
        k=length
    ))

@app.route('/api/player/songs/<int:song_id>', methods=['GET'])
def get_song_detail(song_id):
    """Endpoint untuk mendapatkan detail lagu"""
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    id, judul as title, artis as artist,
                    nama_file_audio as audio_file, 
                    thumbnail as cover_url,
                    duration, plays, likes,
                    deskripsi as description,
                    genre
                FROM lagu
                WHERE id = %s
            """, (song_id,))
            song = cursor.fetchone()
            
            if not song:
                return jsonify({'error': 'Lagu tidak ditemukan'}), 404
                
            return jsonify({
                'id': song['id'],
                'judul': song['title'],
                'artis': song['artist'],
                'deskripsi': song['description'],
                'thumbnail': f"{song['cover_url']}",
                'audio_url': f"/data/audio/{song['audio_file']}",
                'genre': song['genre'] or 'other'
            })
    except Exception as e:
        logger.error(f"Error getting song detail: {e}")
        return jsonify({'error': 'Gagal mengambil detail lagu'}), 500
    finally:
        conn.close()

#Endpoint play
@app.route('/api/player/songs/<int:song_id>/play', methods=['POST'])
def track_play(song_id):
    """Endpoint untuk mencatat pemutaran lagu"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE lagu SET plays = plays + 1 
                WHERE id = %s
            """, (song_id,))
            conn.commit()
            
            # Get updated play count
            cursor.execute("SELECT plays FROM lagu WHERE id = %s", (song_id,))
            plays = cursor.fetchone()[0]
            
            return jsonify({
                'plays': plays
            }), 200
            
    except Exception as e:
        logger.error(f"Play tracking error: {str(e)}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

#Endpoint like
@app.route('/api/user/likes/<int:song_id>', methods=['POST'])
def toggle_like(song_id):
    """Endpoint untuk like/unlike lagu"""
    # Check authentication
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'error': 'Unauthorized',
            'message': 'Anda harus login untuk melakukan like'
        }), 401

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 1. Verifikasi lagu ada
            cursor.execute("SELECT id FROM lagu WHERE id = %s", (song_id,))
            song = cursor.fetchone()
            if not song:
                return jsonify({
                    'success': False,
                    'error': 'Not Found',
                    'message': 'Lagu tidak ditemukan'
                }), 404

            # 2. Check status like saat ini
            cursor.execute("""
                SELECT 1 FROM user_likes 
                WHERE user_id = %s AND song_id = %s
                LIMIT 1
            """, (session['user_id'], song_id))
            
            is_liked = cursor.fetchone() is not None
            
            if is_liked:
                # 3. Unlike - hapus dari user_likes
                cursor.execute("""
                    DELETE FROM user_likes 
                    WHERE user_id = %s AND song_id = %s
                """, (session['user_id'], song_id))
                
                # Kurangi jumlah like (pastikan tidak negatif)
                cursor.execute("""
                    UPDATE lagu 
                    SET likes = GREATEST(0, likes - 1) 
                    WHERE id = %s
                """, (song_id,))
                
                action = 'unliked'
            else:
                # 4. Like - tambahkan ke user_likes
                try:
                    cursor.execute("""
                        INSERT INTO user_likes (user_id, song_id)
                        VALUES (%s, %s)
                    """, (session['user_id'], song_id))
                except pymysql.err.IntegrityError:
                    # Handle kemungkinan duplicate like
                    conn.rollback()
                    return jsonify({
                        'success': False,
                        'error': 'Already Liked',
                        'message': 'Anda sudah menyukai lagu ini'
                    }), 400
                
                # Tambah jumlah like
                cursor.execute("""
                    UPDATE lagu 
                    SET likes = likes + 1 
                    WHERE id = %s
                """, (song_id,))
                
                action = 'liked'
            
            conn.commit()
            
            # 5. Dapatkan jumlah like terbaru
            cursor.execute("SELECT likes FROM lagu WHERE id = %s", (song_id,))
            result = cursor.fetchone()
            likes = result['likes'] if result else 0
            
            return jsonify({
                'success': True,
                'action': action,
                'likes': likes,
                'message': f'Berhasil {action} lagu'
            }), 200
            
    except pymysql.MySQLError as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error in like: {e.args[0]} - {e.args[1]}")
        return jsonify({
            'success': False,
            'error': 'Database Error',
            'message': 'Terjadi kesalahan database',
            'db_error_code': e.args[0],
            'db_error_msg': e.args[1]
        }), 500
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error in like: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'Terjadi kesalahan tak terduga'
        }), 500
    finally:
        if conn:
            conn.close()
            
@app.route('/api/user/likes', methods=['GET'])
def get_liked_songs():
    """Endpoint untuk mendapatkan semua lagu yang disukai oleh pengguna"""
    
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT lagu.id, lagu.judul, lagu.artis, lagu.likes, lagu.thumbnail 
                FROM lagu 
                JOIN user_likes ON lagu.id = user_likes.song_id 
                WHERE user_likes.user_id = %s
            """, (session['user_id'],))
            songs = cursor.fetchall()

            # Pastikan thumbnail URL disiapkan dengan benar
            for song in songs:
                song['thumbnail'] = url_for('serve_public', filename=f'thumbs/{song["thumbnail"]}')
                song['judul'] = song['judul'] or 'Untitled'  # Menambahkan default judul jika kosong

            return jsonify(songs), 200

    except pymysql.MySQLError as e:
        logger.error(f"Database error in get_liked_songs: {e.args[0]} - {e.args[1]}")
        return jsonify({
            'success': False,
            'error': 'Database Error',
            'message': 'Terjadi kesalahan database',
            'db_error_code': e.args[0],
            'db_error_msg': e.args[1]
        }), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_liked_songs: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'Terjadi kesalahan tak terduga'
        }), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/player/playlists', methods=['GET'])
def get_all_playlists():
    """Endpoint untuk mendapatkan semua playlist"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name FROM playlists")
            playlists = cursor.fetchall()
            return jsonify(playlists)
    except Exception as e:
        logger.error(f"Error getting playlists: {e}")
        return jsonify({'error': 'Gagal mengambil playlist'}), 500
    finally:
        conn.close()

@app.route('/api/player/playlists/<int:playlist_id>', methods=['GET'])
def get_playlist_songs(playlist_id):
    """Endpoint untuk mendapatkan lagu dalam playlist"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    l.id, l.judul AS title, l.artis AS artist,
                    CONCAT('/data/audio/', l.nama_file_audio) AS audio_url,
                    CONCAT('/public/thumbs/', l.thumbnail) AS cover_url,
                    l.duration
                FROM lagu l
                JOIN playlist_songs ps ON l.id = ps.song_id
                WHERE ps.playlist_id = %s
            """, (playlist_id,))
            songs = cursor.fetchall()
            return jsonify(songs)
    except Exception as e:
        logger.error(f"Error getting playlist songs: {e}")
        return jsonify({'error': 'Gagal mengambil lagu playlist'}), 500
    finally:
        conn.close()

@app.route('/api/player/search', methods=['GET'])
def search_songs():
    """Endpoint untuk mencari lagu"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Parameter pencarian diperlukan'}), 400
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    id, judul AS title, artis AS artist,
                    CONCAT('/data/audio/', nama_file_audio) AS audio_url,
                    CONCAT('/public/thumbs/', thumbnail) AS cover_url
                FROM lagu
                WHERE judul LIKE %s OR artis LIKE %s
                LIMIT 20
            """, (f"%{query}%", f"%{query}%"))
            results = cursor.fetchall()
            return jsonify(results)
    except Exception as e:
        logger.error(f"Error searching songs: {e}")
        return jsonify({'error': 'Gagal melakukan pencarian'}), 500
    finally:
        conn.close()

@app.route('/api/upload', methods=['POST'])
def upload_song():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    # Cek apakah request mengandung file atau URL
    if 'file' in request.files:
        return handle_file_upload(request)
    elif request.json and 'url' in request.json:
        return handle_url_upload(request.json['url'])
    else:
        return jsonify({'error': 'File atau URL diperlukan'}), 400

def handle_file_upload(request):
    """Tangani upload file audio langsung"""
    audio_file = request.files['file']
    
    # Validasi file
    if not audio_file or audio_file.filename == '':
        return jsonify({'error': 'File tidak valid'}), 400
        
    # Cek ekstensi file
    allowed_extensions = {'mp3', 'wav', 'ogg', 'm4a', 'flac'}
    if '.' not in audio_file.filename or \
       audio_file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({
            'error': 'Format file tidak didukung',
            'supported_formats': list(allowed_extensions)
        }), 400
        
    # Proses metadata
    title = request.form.get('title', 'Untitled')
    artist = request.form.get('artist', 'Unknown Artist')
    genre = request.form.get('genre', 'other')
    
    # Cek duplikasi
    if check_duplicate_song(title, artist):
        return jsonify({
            'error': 'Lagu sudah ada',
            'code': 'DUPLICATE_SONG'
        }), 409
        
    # Simpan file
    try:
        # Buat nama file unik
        file_ext = audio_file.filename.rsplit('.', 1)[1].lower()
        unique_id = secrets.token_hex(4)
        filename = f"{secure_filename(title)}_{unique_id}.{file_ext}"
        
        # Simpan file audio
        audio_dir = os.path.join('data', 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        filepath = os.path.join(audio_dir, filename)
        audio_file.save(filepath)
        
        # Proses thumbnail
        thumbnail_file = request.files.get('thumbnail')
        thumbnail_filename = None
        
        if thumbnail_file and thumbnail_file.filename != '':
            # Validasi thumbnail
            if '.' not in thumbnail_file.filename or \
               thumbnail_file.filename.rsplit('.', 1)[1].lower() not in {'jpg', 'jpeg', 'png'}:
                return jsonify({'error': 'Thumbnail harus JPG/PNG'}), 400
                
            thumbnail_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower()
            thumbnail_filename = f"{unique_id}.{thumbnail_ext}"
            
            # Simpan thumbnail
            thumb_dir = os.path.join('public', 'thumbs')
            os.makedirs(thumb_dir, exist_ok=True)
            thumbnail_file.save(os.path.join(thumb_dir, thumbnail_filename))
        else:
            # Gunakan thumbnail default
            thumbnail_filename = 'default.jpg'
        
        # Simpan ke database
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO lagu (
                    judul, artis, deskripsi, 
                    nama_file_audio, thumbnail, 
                    genre, user_id, tanggal_upload,
                    random_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """, (
                title, 
                artist,
                request.form.get('description', ''),
                filename,
                thumbnail_filename,
                genre,
                session['user_id'],
                secrets.token_hex(8)
            ))
            song_id = cursor.lastrowid
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Lagu berhasil diupload',
            'song_id': song_id,
            'title': title,
            'artist': artist,
            'audio_url': f"/data/audio/{filename}",
            'thumbnail_url': f"/public/thumbs/{thumbnail_filename}"
        }), 201
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        # Hapus file yang sudah terupload jika ada error
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({
            'error': 'Gagal mengupload file',
            'detail': str(e)
        }), 500

def handle_url_upload(url):
    """Tangani upload dari URL YouTube/Spotify"""
    try:
        if 'spotify.com' in url:
            result, error = download_from_spotify(url)
        elif 'youtube.com' in url or 'youtu.be' in url:
            result, error = download_from_youtube(url)
        else:
            return jsonify({
                'error': 'URL tidak didukung',
                'supported': ['YouTube', 'Spotify']
            }), 400
            
        if error:
            return jsonify({'error': error}), 500
            
        return jsonify(result), 201
        
    except Exception as e:
        logger.error(f"URL upload error: {e}")
        return jsonify({
            'error': 'Gagal memproses URL',
            'detail': str(e)
        }), 500
# ======================
# ENDPOINT STREAMING
# ======================

@app.route('/data/audio/<path:filename>')
def serve_audio(filename):
    """Endpoint untuk streaming audio"""
    return send_from_directory('data/audio', filename)

@app.route('/public/thumbs/<path:filename>')
def serve_thumbnail(filename):
    """Endpoint untuk gambar thumbnail"""
    return send_from_directory('public/thumbs', filename)

# ======================
# ENDPOINT AUTH
# ======================
# ===== OAuth Login =====
@app.route('/login/<provider>')
def login2(provider):
    redirect_uri = url_for('auth', provider=provider, _external=True)
    client = oauth.create_client(provider)
    if not client:
        return f"Provider '{provider}' tidak dikenali", 400
    return client.authorize_redirect(redirect_uri)

@app.route('/auth/<provider>')
def auth(provider):
    client = oauth.create_client(provider)
    if not client:
        return f"Provider '{provider}' tidak dikenali", 400

    token = client.authorize_access_token()

    if provider == 'github':
        user_info = client.get('user').json()
        session['user'] = {
            'provider': provider,
            'name': user_info.get('name'),
            'username': user_info.get('login'),
            'avatar': user_info.get('avatar_url'),
        }

    elif provider == 'google':
        resp = client.get('https://openidconnect.googleapis.com/v1/userinfo')
        user_info = resp.json()
        session['user'] = {
            'provider': provider,
            'name': user_info.get('name'),
            'username': user_info.get('email'),
            'avatar': user_info.get('picture'),
        }

    elif provider == 'facebook':
        user_info = client.get('me?fields=id,name,email,picture.width(200)').json()
        session['user'] = {
            'provider': provider,
            'name': user_info.get('name'),
            'username': user_info.get('email'),
            'avatar': user_info['picture']['data']['url'],
        }

    email = session['user']['username']
    name = session['user']['name']
    avatar = session['user']['avatar']

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, is_verified FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

            if not existing_user:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, is_verified, created_at, last_login, foto_profile)
                    VALUES (%s, %s, '', 1, NOW(), NOW(), %s)
                """, (name, email, avatar))
                conn.commit()

                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                new_user = cursor.fetchone()
                session['user_id'] = new_user['id']
                session['username'] = name
            else:
                session['user_id'] = existing_user['id']
                session['username'] = existing_user['username']

                # Update avatar jika user login ulang
                cursor.execute("UPDATE users SET foto_profile = %s WHERE id = %s", (avatar, existing_user['id']))

                if existing_user['is_verified'] == 0:
                    cursor.execute("UPDATE users SET is_verified = 1 WHERE id = %s", (existing_user['id'],))

                conn.commit()

    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({'error': 'Terjadi kesalahan pada server'}), 500
    finally:
        conn.close()

    return redirect('/')

# ===== Register =====
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    required_fields = ['username', 'email', 'password']
    
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Semua field harus diisi'}), 400

    username = data['username']
    email = data['email']
    password = data['password']

    if len(username) < 3 or len(username) > 20:
        return jsonify({'error': 'Username harus 3-20 karakter'}), 400
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({'error': 'Username hanya boleh huruf, angka, dan underscore'}), 400
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({'error': 'Format email tidak valid'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password minimal 8 karakter'}), 400

    conn = None
    try:
        salt = bcrypt.gensalt(rounds=14)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        verification_code = secrets.token_urlsafe(32)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users 
                (username, email, password_hash, verification_code, created_at, last_login)
                VALUES (%s, %s, %s, %s, NOW(), NULL)
            """, (username, email, hashed, verification_code))
            conn.commit()

        Thread(target=send_verification_email, args=(email, verification_code)).start()
        return jsonify({'message': 'Registrasi berhasil. Silakan cek email untuk verifikasi.', 'status': 'pending_verification'}), 201

    except pymysql.err.IntegrityError as e:
        error_str = str(e).lower()
        if 'username' in error_str:
            return jsonify({'error': 'Username sudah digunakan'}), 409
        elif 'email' in error_str:
            return jsonify({'error': 'Email sudah terdaftar'}), 409
        return jsonify({'error': 'Registrasi gagal'}), 500
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Terjadi kesalahan server'}), 500
    finally:
        if conn:
            conn.close()

# ===== Request Password Reset =====
@app.route('/api/auth/request-reset', methods=['POST'])
def request_password_reset():
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'Email diperlukan'}), 400

    email = data['email']
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s AND is_verified = 1", (email,))
            user = cursor.fetchone()

            if not user:
                return jsonify({'error': 'Email tidak terdaftar atau belum terverifikasi'}), 404

            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)

            cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, token, expires_at)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE token = VALUES(token), expires_at = VALUES(expires_at)
            """, (user['id'], reset_token, expires_at))
            conn.commit()

            send_reset_email(email, reset_token)
            return jsonify({'message': 'Instruksi reset password telah dikirim ke email Anda'}), 200

    except Exception as e:
        logger.error(f"Reset request error: {e}")
        return jsonify({'error': 'Gagal memproses permintaan reset'}), 500
    finally:
        if conn:
            conn.close()

# ===== Reset Password =====
@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    if not data or 'token' not in data or 'new_password' not in data:
        return jsonify({'error': 'Token dan password baru diperlukan'}), 400

    token = data['token']
    new_password = data['new_password']

    if len(new_password) < 8:
        return jsonify({'error': 'Password minimal 8 karakter'}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM password_reset_tokens WHERE token = %s AND expires_at > NOW()", (token,))
            token_data = cursor.fetchone()

            if not token_data:
                return jsonify({'error': 'Token tidak valid atau sudah kadaluarsa'}), 400

            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt(rounds=14))

            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed, token_data['user_id']))
            cursor.execute("DELETE FROM password_reset_tokens WHERE token = %s", (token,))
            conn.commit()

            return jsonify({'message': 'Password berhasil direset. Silakan login dengan password baru.'}), 200
    except Exception as e:
        logger.error(f"Reset error: {e}")
        return jsonify({'error': 'Gagal reset password'}), 500
    finally:
        if conn:
            conn.close()

# ===== Verifikasi Email =====
@app.route('/api/auth/verify', methods=['GET'])
def verify():
    code = request.args.get('code')
    if not code:
        return render_template('message.html', status='error', message='Verification code required'), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE verification_code = %s", (code,))
            result = cursor.fetchone()

            if not result:
                return render_template('message.html', status='error', message='Invalid verification code'), 400

            cursor.execute("UPDATE users SET is_verified = TRUE, verification_code = NULL WHERE verification_code = %s", (code,))
            conn.commit()

        return render_template('message.html', status='success', message='Account verified successfully'), 200
    except Exception as e:
        logger.error(f"Verification error: {e}")
        return render_template('message.html', status='error', message='Verification failed'), 500
    finally:
        if conn:
            conn.close()

# ===== Login =====
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'email_or_username' not in data or 'password' not in data:
        return jsonify({'error': 'Email/username dan password diperlukan'}), 400

    email_or_username = data['email_or_username']
    password = data['password']

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, email, password_hash, is_verified
                FROM users
                WHERE email = %s OR username = %s
            """, (email_or_username, email_or_username))
            user = cursor.fetchone()

            if not user:
                return jsonify({'error': 'Email/username atau password salah'}), 401

            if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                return jsonify({'error': 'Email/username atau password salah'}), 401

            if not user['is_verified']:
                return jsonify({'error': 'Akun belum diverifikasi'}), 403

            session['user_id'] = user['id']
            session['username'] = user['username']

            return jsonify({'message': 'Login berhasil', 'user': {'id': user['id'], 'username': user['username'], 'email': user['email']}}), 200
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login gagal'}), 500
    finally:
        if conn:
            conn.close()

# ===== Logout =====
@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout berhasil'}), 200

# ===== Auth Status =====
@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    if 'user_id' not in session:
        return jsonify({'isLoggedIn': False}), 200

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()

            if not user:
                session.clear()
                return jsonify({'isLoggedIn': False}), 200

            return jsonify({'isLoggedIn': True, 'user': user}), 200
    except Exception as e:
        logger.error(f"Auth status error: {e}")
        return jsonify({'isLoggedIn': False}), 200
    finally:
        if conn:
            conn.close()

#=======================
#ENDPOIN ADMIN DAN EDIT
#=======================

#Hapus akun
@app.route('/api/account/delete', methods=['DELETE'])
def delete_account():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    user_id = session['user_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

        session.clear()
        return jsonify({'message': 'Account deleted successfully'})
    except Exception as e:
        print(traceback.format_exc())  # Ini akan tampilkan error lengkap di terminal
        return jsonify({'message': 'Internal server error'}), 500
    finally:
        conn.close()

# GET all users
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Query yang kompatibel dengan struktur tabel yang ada
            cursor.execute("""
                SELECT 
                    id,
                    username,
                    email,
                    is_verified,  # Asumsi kolom ini ada
                    created_at,
                    last_login
                FROM users
                ORDER BY created_at DESC
            """)
            users = cursor.fetchall()
            
            # Format response dengan nilai default untuk is_active
            formatted_users = []
            for user in users:
                formatted_users.append({
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'is_active': True,  # Default value jika kolom tidak ada
                    'is_verified': bool(user.get('is_verified', False)),
                    'created_at': user['created_at'].strftime('%Y-%m-%d %H:%M:%S') if user['created_at'] else 'N/A',
                    'last_login': user['last_login'].strftime('%Y-%m-%d %H:%M:%S') if user['last_login'] else 'Never'
                })
            
            return jsonify(formatted_users)
            
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch users',
            'details': str(e),
            'suggestion': 'Please check if the users table has required columns'
        }), 500
    finally:
        if conn:
            conn.close()

# GET count of users
@app.route('/api/users/count', methods=['GET'])
def get_users_count():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users;')
    count = cur.fetchone()['count']
    cur.close()
    conn.close()
    return jsonify({'count': count})

# GET single user by ID
@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s;', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user)

@app.route('/api/player/songs/update', methods=['POST'])
def update_song():
    """Update song information"""
    if 'song_id' not in request.form:
        return jsonify({'error': 'ID lagu diperlukan'}), 400
        
    song_id = request.form['song_id']
    
    # Get current data for comparison
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT judul, artis, deskripsi, genre, thumbnail 
                FROM lagu WHERE id = %s
            """, (song_id,))
            current_data = cursor.fetchone()
            
            if not current_data:
                return jsonify({'error': 'Lagu tidak ditemukan'}), 404
                
        # Prepare update data
        update_fields = {}
        new_thumbnail = None
        
        # Check text fields for changes
        text_fields = ['judul', 'artis', 'deskripsi', 'genre']
        for field in text_fields:
            if field in request.form and request.form[field] != current_data[field]:
                update_fields[field] = request.form[field]
        
        # Handle thumbnail upload
        if 'thumbnail' in request.files:
            file = request.files['thumbnail']
            if file.filename != '':
                # Validate file type
                if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    return jsonify({'error': 'Hanya file JPG/JPEG/PNG yang diperbolehkan'}), 400
                
                # Save new thumbnail
                filename = secure_filename(f"{song_id}_{file.filename}")
                thumb_path = os.path.join('public', 'thumbs', filename)
                file.save(thumb_path)
                new_thumbnail = filename
                update_fields['thumbnail'] = filename
                
                # Delete old thumbnail if it exists and isn't default
                old_thumb = current_data['thumbnail']
                if old_thumb and old_thumb != 'default.jpg':
                    try:
                        os.remove(os.path.join('public', 'thumbs', old_thumb))
                    except OSError as e:
                        logger.warning(f"Gagal menghapus thumbnail lama: {str(e)}")
        
        # Only update if there are changes
        if update_fields:
            set_clause = ", ".join([f"{k} = %s" for k in update_fields])
            values = list(update_fields.values())
            
            # Add updated_at and song_id to the values list
            values.append(datetime.now())
            values.append(song_id)
            
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    UPDATE lagu 
                    SET {set_clause}, updated_at = %s
                    WHERE id = %s
                """, values)
                conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Lagu berhasil diperbarui',
            'thumbnail': new_thumbnail or current_data['thumbnail']
        })
        
    except Exception as e:
        logger.error(f"Error updating song: {str(e)}")
        return jsonify({'error': 'Gagal memperbarui lagu'}), 500
    finally:
        conn.close()

@app.route('/api/player/songs/<int:song_id>', methods=['DELETE'])
def delete_song(song_id):
    """Endpoint untuk menghapus lagu"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get file info first
            cursor.execute("""
                SELECT nama_file_audio, thumbnail 
                FROM lagu WHERE id = %s
            """, (song_id,))
            song = cursor.fetchone()
            
            if not song:
                return jsonify({'error': 'Lagu tidak ditemukan'}), 404
            
            # Delete from database
            cursor.execute("DELETE FROM lagu WHERE id = %s", (song_id,))
            conn.commit()
            
            # Delete audio file
            audio_path = os.path.join('data', 'audio', song['nama_file_audio'])
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            # Delete thumbnail if not default
            if song['thumbnail'] and song['thumbnail'] != 'default.jpg':
                thumb_path = os.path.join('public', 'thumbs', song['thumbnail'])
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            
            return jsonify({
                'success': True,
                'message': 'Lagu berhasil dihapus'
            })
            
    except Exception as e:
        logger.error(f"Error deleting song: {str(e)}")
        return jsonify({'error': 'Gagal menghapus lagu'}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    os.makedirs('data/audio', exist_ok=True)
    os.makedirs('data/thumbs', exist_ok=True)
    os.makedirs('public/thumbs', exist_ok=True)
    
    app.run(host='0.0.0.0', port=3000, debug=True)