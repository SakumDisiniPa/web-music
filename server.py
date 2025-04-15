from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for, Response, stream_with_context, make_response, render_template, send_file
import os
import pymysql
import subprocess
import urllib.request
import smtplib
import re
import shutil
import spotipy
import base64
import time
import logging
import json 
import bcrypt
import secrets
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

load_dotenv()



app = Flask(__name__, static_folder='public', static_url_path='/public')
# Aktifkan minifikasi untuk HTML, CSS, dan JS
minify(app=app, html=True, js=True, cssless=True)
app.secret_key = secrets.token_hex(16)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,  # Pastikan HTTPS digunakan
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

#API Credentials
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

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

# Function untuk mengambil hasil pencarian dari YouTube
def search_youtube(query):
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
        result = ydl.extract_info(f"ytsearch:{query}", download=False)  # Hanya cari, tidak download
        return result['entries']

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
    """Download lagu dari Spotify"""
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

        print(f"Spotify metadata fetched in {time.time() - start_time:.2f}s")
        
        # Gunakan query yang lebih spesifik dan resmi
        search_query = f"{judul} {artis} official audio"
        youtube_url = search_youtube(search_query)

        if not youtube_url:
            return None, "❌ Tidak dapat menemukan lagu di YouTube berdasarkan metadata Spotify"

        deskripsi = f"🎵 Dari Spotify\nAlbum: {album}\nRilis: {release_date}"
        
        return download_from_youtube(
            youtube_url=youtube_url,
            judul=judul,
            artis=artis,
            deskripsi=deskripsi,
            thumbnail_url=cover_url
        )

    except Exception as e:
        logger.error(f"Error processing Spotify track: {e}")
        return None, f"❌ Terjadi kesalahan saat memproses lagu dari Spotify: {str(e)}"

def download_from_youtube(youtube_url, judul=None, artis=None, deskripsi=None, thumbnail_url=None):
    """Download lagu dari YouTube"""
    try:
        start_time = time.time()
        
        # Ambil metadata otomatis jika tidak disediakan
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

        # Buat folder jika belum ada
        audio_dir = os.path.join('data', 'audio')
        thumb_dir = os.path.join('data', 'thumbs')
        os.makedirs(audio_dir, exist_ok=True)
        os.makedirs(thumb_dir, exist_ok=True)

        # Buat nama file yang aman
        safe_title = "".join(c if c.isalnum() or c in " -_" else "-" for c in judul)
        video_id = extract_youtube_id(youtube_url) or datetime.now().strftime("%Y%m%d%H%M%S")
        thumb_file = f"{safe_title}-{video_id}.jpg"
        thumb_path = os.path.join(thumb_dir, thumb_file)

        # Download thumbnail secara sync
        thumbnail_downloaded = False
        if thumbnail_url:
            try:
                urllib.request.urlretrieve(thumbnail_url, thumb_path)
                thumbnail_downloaded = True
                logger.info(f"Thumbnail downloaded from {thumbnail_url}")
            except Exception as e:
                logger.warning(f"Gagal download thumbnail dari URL: {e}")

        # Fallback ke thumbnail YouTube jika perlu
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

        # Download audio dengan yt-dlp
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

        # Cari file yang baru didownload
        downloaded_files = [f for f in os.listdir(audio_dir) if safe_title in f and f.endswith('.mp3')]
        if not downloaded_files:
            return None, 'File audio tidak ditemukan setelah diunduh'
        final_file = downloaded_files[0]

        # Salin thumbnail ke folder public
        public_thumb_dir = os.path.join('public', 'thumbs')
        os.makedirs(public_thumb_dir, exist_ok=True)
        shutil.copyfile(thumb_path, os.path.join(public_thumb_dir, thumb_file))

        # Simpan ke database
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO lagu (judul, artis, deskripsi, nama_file_audio, thumbnail, tanggal_upload) VALUES (%s, %s, %s, %s, %s, %s)",
                (judul, artis, deskripsi, final_file, thumb_file, datetime.now())
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
            'thumbnail': f"/public/thumbs/{thumb_file}"
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
    """Proses playlist Spotify dan unduh via YouTube"""
    tracks = get_spotify_playlist_tracks(playlist_url)
    if not tracks:
        return None, "❌ Gagal mendapatkan track dari playlist Spotify"
    
    results = []
    errors = []
    
    for idx, track in enumerate(tracks):
        try:
            search_query = f"{track['title']} {track['artist']} official audio"
            youtube_url = search_youtube(search_query)
            
            if not youtube_url:
                error_msg = f"🔍 Tidak ditemukan di YouTube: {track['title']} - {track['artist']}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            deskripsi = f"Album: {track['album']} | From Spotify Playlist"
            result, error = download_from_youtube(
                youtube_url,
                track['title'],
                track['artist'],
                deskripsi,
                track.get('cover_url')
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
        'message': f"✅ Playlist selesai. Berhasil: {len(results)}, Gagal: {len(errors)}",
        'downloaded': results,
        'errors': errors
    }, None

def process_youtube_playlist(playlist_url):
    """Proses playlist YouTube biasa"""
    videos = get_youtube_playlist_videos(playlist_url)
    if not videos:
        return None, "❌ Gagal mendapatkan video dari playlist YouTube"
    
    results = []
    errors = []
    
    for video in videos:
        try:
            result, error = download_from_youtube(video['url'])
            
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
        'message': f"✅ Playlist selesai. Berhasil: {len(results)}, Gagal: {len(errors)}",
        'downloaded': results,
        'errors': errors
    }, None

def process_youtube_music_playlist(playlist_url):
    """Proses playlist YouTube Music (ditangani seperti playlist YouTube biasa)"""
    return process_youtube_playlist(playlist_url)

# Halaman utama
@app.route('/')
def index_page():
    try:
        return send_from_directory('public', 'index.html')
    except FileNotFoundError:
        return "Halaman utama sedang dalam pengembangan", 404

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

# Endpoint untuk file audio
@app.route('/data/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory('data/audio', filename)

from flask import send_from_directory

@app.route('/public/<path:filename>')
def serve_public(filename):
    return send_from_directory('public', filename)

@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('data', filename)

#Endpoint untuk incon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )
#Endpint untuk playlist
@app.route('/api/playlists', methods=['GET'])
def get_playlists():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM playlist")
    playlists = cursor.fetchall()
    cursor.close()
    return jsonify(playlists)

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

@app.route('/api/playlist/<int:playlist_id>/songs', methods=['GET'])
def get_songs_by_playlist(playlist_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM lagu WHERE playlist_id = %s", (playlist_id,))
    songs = cursor.fetchall()
    cursor.close()
    return jsonify(songs)

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
            conn.close()

@app.route('/search/youtube')
def search_youtube():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Parameter "q" wajib diisi'}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'extract_flat': True,
            'format': 'bestaudio/best',
        }

        with YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch10:{query}", download=False)

        items = []
        for entry in search_results['entries']:
            if entry:  # Untuk keamanan
                items.append({
                    'id': entry['id'],
                    'title': entry.get('title'),
                    'url': f"https://www.youtube.com/watch?v={entry['id']}",
                    'channel': entry.get('uploader'),
                    'thumbnail': entry.get('thumbnail')
                })

        return jsonify(items)

    except Exception as e:
        print(f"Error saat pencarian YouTube: {e}")
        return jsonify({'error': 'Gagal mengambil hasil dari YouTube'}), 500

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
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Data tidak valid (JSON kosong)'}), 400

    url = data.get('url')
    if not url or not url.startswith('http'):
        return jsonify({'error': 'URL tidak valid'}), 400

    try:
        result = None
        error = None

        if 'spotify.com' in url:
            result, error = download_from_spotify(url)
        elif 'youtube.com' in url or 'youtu.be' in url:
            result, error = download_from_youtube(url)
        else:
            return jsonify({'error': 'Hanya URL YouTube atau Spotify yang didukung'}), 400

        if error:
            logger.error(f"Upload error: {error}")
            return jsonify({'error': error}), 500

        # ✅ Tambahkan fallback jika metadata kosong
        if result:
            result['judul'] = result.get('judul') or 'Judul Tidak Diketahui'
            result['artis'] = result.get('artis') or 'Artis Tidak Diketahui'
            result['deskripsi'] = result.get('deskripsi') or ''

        logger.info(f"Upload berhasil dari {url}")
        return jsonify({
            'success': True,
            'pesan': 'Lagu berhasil diunggah',
            'data': result
        })

    except Exception as e:
        logger.error(f"Upload exception: {e}")
        return jsonify({'error': 'Terjadi kesalahan saat upload'}), 500
        
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

if __name__ == '__main__':
    # Pastikan folder yang diperlukan ada
    os.makedirs('data/audio', exist_ok=True)
    os.makedirs('data/thumbs', exist_ok=True)
    os.makedirs('public/thumbs', exist_ok=True)
    
    app.run(host='0.0.0.0', port=3000, debug=True)