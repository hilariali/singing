"""
Karaoke Shen Web Server
A Flask-based web server for the karaoke application.
Run this file to start the web server.
"""

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
import yt_dlp
import requests
import os
import sqlite3
import json
from datetime import datetime

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

# ============================================
# Database Setup
# ============================================
# Use /data directory on Render (persistent disk), fallback to local for development
DATA_DIR = os.environ.get('RENDER_DISK_PATH', os.path.dirname(__file__))
if os.path.exists('/data'):
    DATA_DIR = '/data'
DB_PATH = os.path.join(DATA_DIR, 'karaoke_lyrics.db')

def init_db():
    """Initialize the SQLite database for caching lyrics."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lyrics_cache (
            video_id TEXT PRIMARY KEY,
            video_title TEXT,
            artist TEXT,
            track TEXT,
            source TEXT,
            lyrics_text TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS manual_lyrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_key TEXT UNIQUE,
            artist TEXT,
            track TEXT,
            lyrics_text TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[DB] Database initialized")

# Initialize database on startup
init_db()

def get_cached_lyrics(video_id):
    """Get lyrics from cache if available."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT lyrics_text, artist, track, source FROM lyrics_cache WHERE video_id = ?', (video_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'lyrics': row[0],
                'artist': row[1],
                'track': row[2],
                'source': row[3]
            }
    except Exception as e:
        print(f"[DB ERROR] {e}")
    return None

def save_lyrics_to_cache(video_id, video_title, artist, track, source, lyrics_text):
    """Save lyrics to the database cache."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute('''
            INSERT OR REPLACE INTO lyrics_cache 
            (video_id, video_title, artist, track, source, lyrics_text, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (video_id, video_title, artist, track, source, lyrics_text, now, now))
        conn.commit()
        conn.close()
        print(f"[DB] Cached lyrics for: {video_title}")
    except Exception as e:
        print(f"[DB SAVE ERROR] {e}")

def search_manual_lyrics(search_key):
    """Search for manually added lyrics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Try exact match first
        c.execute('SELECT lyrics_text, artist, track FROM manual_lyrics WHERE search_key = ?', (search_key.lower(),))
        row = c.fetchone()
        if not row:
            # Try partial match
            c.execute('SELECT lyrics_text, artist, track FROM manual_lyrics WHERE search_key LIKE ?', (f'%{search_key.lower()}%',))
            row = c.fetchone()
        conn.close()
        if row:
            return {
                'lyrics': row[0],
                'artist': row[1],
                'track': row[2],
                'source': 'manual'
            }
    except Exception as e:
        print(f"[DB SEARCH ERROR] {e}")
    return None


# Configure yt-dlp
SEARCH_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
}

STREAM_OPTS = {
    'format': '18/22/best[ext=mp4][vcodec^=avc1][acodec^=mp4a]/best',
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'youtube_include_dash_manifest': False,
    'youtube_include_hls_manifest': False,
    'noplaylist': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory('web', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    """Serve static files from the web directory."""
    return send_from_directory('web', path)


@app.route('/api/search', methods=['GET'])
def search_youtube():
    """Search for videos on YouTube using keywords."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Missing search query'}), 400

    print(f"Searching for: {query}")
    try:
        with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
            search_results = ydl.extract_info(f"ytsearch20:{query}", download=False)
            if not search_results:
                return jsonify([])

            results = []
            entries = search_results.get('entries', [])
            print(f"Found {len(entries)} entries.")

            for entry in entries:
                if entry:
                    thumb = entry.get('thumbnail')
                    if not thumb and entry.get('thumbnails'):
                        thumb = entry.get('thumbnails')[-1].get('url')

                    results.append({
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'thumbnail': thumb,
                        'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                    })
            return jsonify(results)
    except Exception as e:
        import traceback
        print(f"Search error details: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/video_info', methods=['GET'])
def get_video_info():
    """Get info for a single video from a direct URL."""
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Missing URL parameter'}), 400

    print(f"Getting info for URL: {url}")
    try:
        with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({'error': 'Failed to get video info'}), 404

            thumb = info.get('thumbnail')
            if not thumb and info.get('thumbnails'):
                thumb = info.get('thumbnails')[-1].get('url')

            return jsonify({
                'id': info.get('id'),
                'title': info.get('title'),
                'thumbnail': thumb,
                'url': url
            })
    except Exception as e:
        print(f"Info error details: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stream_url', methods=['GET'])
def get_stream_url():
    """Get the local proxy URL for a YouTube video."""
    video_id = request.args.get('id', '').strip()
    if not video_id:
        return jsonify({'error': 'Missing video ID'}), 400

    # Return a local URL that our proxy will handle
    return jsonify({'url': f"/proxy_stream?v={video_id}"})


@app.route('/api/subtitles', methods=['GET'])
def get_subtitles():
    """Get lyrics for a YouTube video - returns plain text for scroll view."""
    video_id = request.args.get('id', '').strip()
    video_title = request.args.get('title', '').strip()  # Optional: pass title to skip yt-dlp
    
    if not video_id:
        return jsonify({'error': 'Missing video ID'}), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"--- [LYRICS] Fetching for: {video_id} ---")
    
    try:
        # Check database cache first
        cached = get_cached_lyrics(video_id)
        if cached:
            print(f"[LYRICS] Found in cache: {cached['source']}")
            return jsonify({
                'available': True,
                'lyrics': cached['lyrics'],
                'artist': cached['artist'],
                'track': cached['track'],
                'source': cached['source'] + ' (cached)'
            })
        
        artist = ''
        track = ''
        
        # If title provided, use it directly (faster)
        if video_title:
            print(f"[LYRICS] Using provided title: {video_title}")
        else:
            # Get video info via yt-dlp (slower)
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_title = info.get('title', '')
                    artist = info.get('artist', '') or info.get('creator', '') or ''
                    track = info.get('track', '')
            except Exception as e:
                print(f"[LYRICS] yt-dlp failed: {e}")
                return jsonify({
                    'available': False,
                    'lyrics': '',
                    'artist': '',
                    'track': '',
                    'source': 'error'
                })
        
        print(f"[LYRICS] Video: {video_title}, Artist: {artist}, Track: {track}")
        
        # Extract song info from title
        extracted_artist, extracted_track = extract_song_info(video_title)
        if not artist:
            artist = extracted_artist
        if not track:
            track = extracted_track
        
        # Check for manual lyrics in database
        search_key = f"{artist} {track}".strip() or video_title
        manual = search_manual_lyrics(search_key)
        if manual:
            print(f"[LYRICS] Found manual lyrics in database")
            save_lyrics_to_cache(video_id, video_title, manual['artist'], manual['track'], 'manual', manual['lyrics'])
            return jsonify({
                'available': True,
                'lyrics': manual['lyrics'],
                'artist': manual['artist'],
                'track': manual['track'],
                'source': 'database'
            })
        
        # Try to fetch from external sources
        lyrics_text = None
        source = None
        
        # Check if Chinese song
        is_chinese = contains_chinese(video_title)
        
        if is_chinese:
            result = fetch_chinese_lyrics(artist, track, video_title)
            if result:
                lyrics_text = result['lyrics']
                source = result['source']
                artist = result.get('artist', artist)
                track = result.get('track', track)
        
        if not lyrics_text:
            result = fetch_english_lyrics(artist, track, video_title)
            if result:
                lyrics_text = result['lyrics']
                source = result['source']
                artist = result.get('artist', artist)
                track = result.get('track', track)
        
        if lyrics_text:
            # Save to cache
            save_lyrics_to_cache(video_id, video_title, artist, track, source, lyrics_text)
            return jsonify({
                'available': True,
                'lyrics': lyrics_text,
                'artist': artist,
                'track': track,
                'source': source
            })
        
        # No lyrics found
        print(f"[LYRICS] No lyrics found for: {video_title}")
        return jsonify({
            'available': False,
            'lyrics': '',
            'artist': artist,
            'track': track,
            'source': 'none'
        })
            
    except Exception as e:
        import traceback
        print(f"[LYRICS ERROR] {e}")
        traceback.print_exc()
        return jsonify({'available': False, 'error': str(e)})


@app.route('/api/save_lyrics', methods=['POST'])
def save_lyrics():
    """Save manually entered lyrics to the database."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    video_id = data.get('video_id', '')
    artist = data.get('artist', '')
    track = data.get('track', '')
    lyrics = data.get('lyrics', '')
    
    if not lyrics:
        return jsonify({'error': 'No lyrics provided'}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        # Save to manual_lyrics table
        search_key = f"{artist} {track}".strip().lower()
        if search_key:
            c.execute('''
                INSERT OR REPLACE INTO manual_lyrics 
                (search_key, artist, track, lyrics_text, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (search_key, artist, track, lyrics, now))
        
        # Also save to cache if video_id provided
        if video_id:
            c.execute('''
                INSERT OR REPLACE INTO lyrics_cache 
                (video_id, video_title, artist, track, source, lyrics_text, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'manual', ?, ?, ?)
            ''', (video_id, f"{artist} - {track}", artist, track, lyrics, now, now))
        
        conn.commit()
        conn.close()
        
        print(f"[DB] Saved manual lyrics: {artist} - {track}")
        return jsonify({'success': True, 'message': 'Lyrics saved'})
        
    except Exception as e:
        print(f"[DB SAVE ERROR] {e}")
        return jsonify({'error': str(e)}), 500


def fetch_chinese_lyrics(artist, track, video_title):
    """Fetch Chinese lyrics from multiple sources, return plain text."""
    print(f"[CHINESE] Searching: artist='{artist}', track='{track}'")
    
    try:
        # Try NetEase first (most comprehensive Chinese library)
        result = search_lyrics_netease(artist, track)
        if result and result.get('lyrics'):
            return result
    except Exception as e:
        print(f"[CHINESE] NetEase error: {e}")
    
    try:
        # Try Genius (works for many Chinese songs too)
        result = search_lyrics_genius(artist, track)
        if result and result.get('lyrics'):
            return result
    except Exception as e:
        print(f"[CHINESE] Genius error: {e}")
    
    try:
        # Try Kugou
        result = search_lyrics_kugou(artist, track)
        if result and result.get('lyrics'):
            return result
    except Exception as e:
        print(f"[CHINESE] Kugou error: {e}")
    
    # Try with just track name if artist was provided
    if artist:
        try:
            result = search_lyrics_netease('', track)
            if result and result.get('lyrics'):
                return result
        except:
            pass
        
        try:
            result = search_lyrics_genius('', track)
            if result and result.get('lyrics'):
                return result
        except:
            pass
    
    return None


def fetch_english_lyrics(artist, track, video_title):
    """Fetch English lyrics from multiple sources, return plain text."""
    print(f"[ENGLISH] Searching: artist='{artist}', track='{track}'")
    
    # Try LRCLIB first (usually most reliable)
    result = search_lyrics_lrclib_simple(artist, track, video_title)
    if result and result.get('lyrics'):
        return result
    
    # Try Genius API
    result = search_lyrics_genius(artist, track)
    if result and result.get('lyrics'):
        return result
    
    # Try lyrics.ovh as fallback
    result = search_lyrics_ovh_simple(artist, track)
    if result and result.get('lyrics'):
        return result
    
    return None


def search_lyrics_genius(artist, track):
    """Search for lyrics using Genius API."""
    try:
        if not track:
            return None
        
        search_term = f"{artist} {track}".strip() if artist else track
        print(f"[GENIUS] Searching: '{search_term}'")
        
        # Genius search API (public, no auth needed)
        search_url = "https://genius.com/api/search/multi"
        params = {'q': search_term}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"[GENIUS] Search failed: {response.status_code}")
            return None
        
        data = response.json()
        sections = data.get('response', {}).get('sections', [])
        
        # Find song section
        for section in sections:
            if section.get('type') == 'song':
                hits = section.get('hits', [])
                if hits:
                    song = hits[0].get('result', {})
                    song_url = song.get('url', '')
                    song_title = song.get('title', track)
                    song_artist = song.get('primary_artist', {}).get('name', artist)
                    
                    if song_url:
                        # Fetch lyrics from page
                        lyrics = fetch_genius_lyrics_page(song_url)
                        if lyrics:
                            print(f"[GENIUS] Found lyrics: {song_artist} - {song_title}")
                            return {
                                'lyrics': lyrics,
                                'source': 'genius',
                                'track': song_title,
                                'artist': song_artist,
                            }
        return None
        
    except Exception as e:
        print(f"[GENIUS ERROR] {e}")
        return None


def fetch_genius_lyrics_page(url):
    """Fetch lyrics from a Genius song page."""
    try:
        import re
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Extract lyrics from the page using regex
        # Genius stores lyrics in data-lyrics-container divs
        lyrics_parts = []
        
        # Method 1: Look for Lyrics__Container
        pattern = r'<div[^>]*class="[^"]*Lyrics__Container[^"]*"[^>]*>(.*?)</div>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            # Clean HTML
            text = re.sub(r'<br\s*/?>', '\n', match)
            text = re.sub(r'<[^>]+>', '', text)
            text = text.strip()
            if text:
                lyrics_parts.append(text)
        
        if lyrics_parts:
            return '\n\n'.join(lyrics_parts)
        
        # Method 2: Look for JSON embedded lyrics
        pattern = r'"lyrics":\s*\{"body":\s*\{"html":\s*"([^"]+)"'
        match = re.search(pattern, html)
        if match:
            lyrics_html = match.group(1)
            lyrics_html = lyrics_html.encode().decode('unicode_escape')
            text = re.sub(r'<br\s*/?>', '\n', lyrics_html)
            text = re.sub(r'<[^>]+>', '', text)
            return text.strip()
        
        return None
        
    except Exception as e:
        print(f"[GENIUS PAGE ERROR] {e}")
        return None


def contains_chinese(text):
    """Check if text contains Chinese characters."""
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


def extract_song_info(video_title):
    """Extract artist and track from video title with better parsing."""
    import re
    
    original_title = video_title
    clean_title = video_title
    
    # Remove common video title patterns
    patterns_to_remove = [
        r'\s*[\(\[【「].*?(?:官方|official|mv|music video|lyric|歌詞|完整版|高音質|hd|4k|1080p|live|現場|演唱會).*?[\)\]】」]',
        r'\s*[\(\[【「].*?[\)\]】」]',
        r'\s*[-–—]\s*(?:official|mv|music video|lyric|歌詞).*$',
        r'\s*\|.*$',
        r'\s*\/.*$',
        r'\s*官方.*$',
        r'\s*MV$',
        r'\s*Official\s*(?:Music\s*)?(?:Video)?$',
    ]
    for pattern in patterns_to_remove:
        clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
    clean_title = clean_title.strip()
    
    artist = ''
    track = ''
    
    # Pattern 1: Artist《Song》or Artist「Song」
    match = re.match(r'^(.+?)\s*[《「](.+?)[》」]\s*$', clean_title)
    if match:
        artist = match.group(1).strip()
        track = match.group(2).strip()
        return artist, track
    
    # Pattern 2: Artist - Song
    match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', clean_title)
    if match:
        artist = match.group(1).strip()
        track = match.group(2).strip()
        return artist, track
    
    # Pattern 3: Song - Artist (reverse)
    # For cases like "歌名 - 歌手"
    
    # No separator found, use whole title as track
    track = clean_title
    
    return artist, track


def search_lyrics_netease(artist, track):
    """Search for lyrics from NetEase Music API (163 Music) - returns plain text."""
    try:
        import json
        import re
        
        # Search for the song - try both original and simplified search terms
        search_term = f"{artist} {track}".strip() if artist else track
        
        # Use the CloudMusic API endpoint (more reliable)
        search_url = "https://music.163.com/api/search/get/web"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://music.163.com/',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        params = {
            's': search_term,
            'type': 1,  # 1 = songs
            'limit': 15,
            'offset': 0
        }
        
        print(f"[NETEASE] Searching: '{search_term}'")
        response = requests.post(search_url, data=params, headers=headers, timeout=8)
        
        if response.status_code != 200:
            print(f"[NETEASE] Search failed: {response.status_code}")
            return None
        
        data = response.json()
        result = data.get('result', {})
        if isinstance(result, str):
            print(f"[NETEASE] Unexpected result format")
            return None
        songs = result.get('songs', []) if isinstance(result, dict) else []
        
        if not songs:
            # Try with just track name (remove artist)
            if artist and track:
                params['s'] = track
                response = requests.post(search_url, data=params, headers=headers, timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('result', {})
                    songs = result.get('songs', []) if isinstance(result, dict) else []
        
        if not songs:
            print(f"[NETEASE] No songs found")
            return None
        
        # Try to find lyrics for each song
        for song in songs[:5]:
            song_id = song.get('id')
            song_name = song.get('name', '')
            artists = song.get('artists', [])
            artist_name = artists[0].get('name', '') if artists else ''
            
            # Get lyrics using a different endpoint
            lyrics_url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
            lyrics_response = requests.get(lyrics_url, headers=headers, timeout=5)
            
            if lyrics_response.status_code != 200:
                continue
            
            lyrics_data = lyrics_response.json()
            lrc_content = lyrics_data.get('lrc', {}).get('lyric', '')
            
            if lrc_content:
                # Convert LRC to plain text (remove timestamps)
                plain_lyrics = lrc_to_plain_text(lrc_content)
                if plain_lyrics and len(plain_lyrics.split('\n')) > 3:
                    print(f"[NETEASE] Found lyrics: {artist_name} - {song_name}")
                    return {
                        'lyrics': plain_lyrics,
                        'source': 'netease',
                        'track': song_name,
                        'artist': artist_name,
                    }
        
        return None
        
    except Exception as e:
        print(f"[NETEASE ERROR] {e}")
        return None


def lrc_to_plain_text(lrc_content):
    """Convert LRC format to plain text by removing timestamps."""
    import re
    lines = []
    for line in lrc_content.split('\n'):
        # Remove timestamp patterns like [00:12.34]
        text = re.sub(r'\[\d{1,2}:\d{2}[\.:,]?\d{0,3}\]', '', line).strip()
        # Skip metadata lines like [ti:Title] [ar:Artist]
        if text and not re.match(r'^\[.*\]$', line.strip()):
            lines.append(text)
    return '\n'.join(lines)


def search_lyrics_qq(artist, track):
    """Search for synced lyrics from QQ Music API."""
    try:
        import json
        
        search_term = f"{artist} {track}".strip() if artist else track
        
        # QQ Music search API (newer endpoint)
        search_url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://y.qq.com/',
            'Origin': 'https://y.qq.com'
        }
        
        # Build the request payload
        payload = {
            "music.search.SearchCgiService": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {
                    "query": search_term,
                    "num_per_page": 10,
                    "page_num": 1,
                    "search_type": 0
                }
            }
        }
        
        print(f"[QQMUSIC] Searching: '{search_term}'")
        response = requests.post(search_url, json=payload, headers=headers, timeout=5)
        
        if response.status_code != 200:
            print(f"[QQMUSIC] Search failed: {response.status_code}")
            return None
        
        data = response.json()
        songs = data.get('music.search.SearchCgiService', {}).get('data', {}).get('body', {}).get('song', {}).get('list', [])
        
        if not songs:
            print(f"[QQMUSIC] No songs found")
            return None
        
        for song in songs[:5]:
            song_mid = song.get('mid')
            song_name = song.get('name', '')
            singers = song.get('singer', [])
            artist_name = singers[0].get('name', '') if singers else ''
            
            if not song_mid:
                continue
            
            # Get lyrics using newer API
            lyrics_url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
            lyrics_params = {
                'songmid': song_mid,
                'g_tk': '5381',
                'format': 'json',
                'nobase64': 1
            }
            lyrics_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://y.qq.com/'
            }
            
            lyrics_response = requests.get(lyrics_url, params=lyrics_params, headers=lyrics_headers, timeout=3)
            
            if lyrics_response.status_code == 200:
                try:
                    lyrics_text = lyrics_response.text
                    # Handle JSONP callback
                    if 'callback' in lyrics_text or 'MusicJsonCallback' in lyrics_text:
                        import re
                        match = re.search(r'\{.*\}', lyrics_text, re.DOTALL)
                        if match:
                            lyrics_text = match.group()
                    
                    lyrics_data = json.loads(lyrics_text)
                    lrc_content = lyrics_data.get('lyric', '')
                    
                    if lrc_content:
                        # Decode base64 if needed
                        import base64
                        try:
                            lrc_content = base64.b64decode(lrc_content).decode('utf-8')
                        except:
                            pass
                        
                        captions = parse_lrc(lrc_content)
                        if captions and len(captions) > 3:
                            print(f"[QQMUSIC] Found lyrics: {artist_name} - {song_name}")
                            return {
                                'available': True,
                                'source': 'qqmusic',
                                'track': song_name,
                                'artist': artist_name,
                                'synced': True,
                                'languages': ['zh'],
                                'language': 'zh',
                                'captions': captions
                            }
                except Exception as e:
                    print(f"[QQMUSIC] Lyrics parse error: {e}")
                    continue
        
        return None
        
    except Exception as e:
        print(f"[QQMUSIC ERROR] {e}")
        return None


def search_lyrics_kugou(artist, track):
    """Search for synced lyrics from Kugou Music API."""
    try:
        import json
        import hashlib
        
        search_term = f"{artist} {track}".strip() if artist else track
        
        # Kugou search API
        search_url = "https://mobilecdn.kugou.com/api/v3/search/song"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        params = {
            'format': 'json',
            'keyword': search_term,
            'page': 1,
            'pagesize': 10,
            'showtype': 1
        }
        
        print(f"[KUGOU] Searching: '{search_term}'")
        response = requests.get(search_url, params=params, headers=headers, timeout=5)
        
        if response.status_code != 200:
            print(f"[KUGOU] Search failed: {response.status_code}")
            return None
        
        data = response.json()
        songs = data.get('data', {}).get('info', [])
        
        if not songs:
            print(f"[KUGOU] No songs found")
            return None
        
        for song in songs[:5]:
            song_hash = song.get('hash')
            song_name = song.get('songname', '')
            artist_name = song.get('singername', '')
            
            if not song_hash:
                continue
            
            # Get lyrics - Kugou requires a hash-based lookup
            # First get the accesskey
            lyrics_search_url = "https://krcs.kugou.com/search"
            lyrics_params = {
                'ver': 1,
                'man': 'yes',
                'client': 'mobi',
                'keyword': f"{song_name}",
                'duration': song.get('duration', 0) * 1000,
                'hash': song_hash
            }
            
            lyrics_response = requests.get(lyrics_search_url, params=lyrics_params, headers=headers, timeout=5)
            
            if lyrics_response.status_code == 200:
                try:
                    lyrics_data = lyrics_response.json()
                    candidates = lyrics_data.get('candidates', [])
                    
                    if candidates:
                        # Get the first candidate's lyrics
                        candidate = candidates[0]
                        access_key = candidate.get('accesskey')
                        lrc_id = candidate.get('id')
                        
                        if access_key and lrc_id:
                            # Download the actual lyrics
                            download_url = "https://lyrics.kugou.com/download"
                            download_params = {
                                'ver': 1,
                                'client': 'pc',
                                'id': lrc_id,
                                'accesskey': access_key,
                                'fmt': 'lrc',
                                'charset': 'utf8'
                            }
                            
                            download_response = requests.get(download_url, params=download_params, headers=headers, timeout=5)
                            
                            if download_response.status_code == 200:
                                dl_data = download_response.json()
                                lrc_content_b64 = dl_data.get('content', '')
                                
                                if lrc_content_b64:
                                    import base64
                                    lrc_content = base64.b64decode(lrc_content_b64).decode('utf-8')
                                    captions = parse_lrc(lrc_content)
                                    
                                    if captions and len(captions) > 3:
                                        print(f"[KUGOU] Found lyrics: {artist_name} - {song_name}")
                                        # Convert LRC to plain text
                                        plain_lyrics = lrc_to_plain_text(lrc_content)
                                        return {
                                            'lyrics': plain_lyrics,
                                            'source': 'kugou',
                                            'track': song_name,
                                            'artist': artist_name,
                                        }
                except Exception as e:
                    print(f"[KUGOU] Lyrics parse error: {e}")
                    continue
        
        return None
        
    except Exception as e:
        print(f"[KUGOU ERROR] {e}")
        return None


def search_lyrics_lrclib_simple(artist, track, video_title):
    """Search for lyrics from LRCLIB API - returns plain text."""
    try:
        import re
        
        # Clean up title if no track provided
        if not track:
            clean_title = video_title
            patterns_to_remove = [
                r'\s*[\(\[【「].*?[\)\]】」]',
                r'\s*[-–—]\s*(?:official|mv|music video|lyric|歌詞).*$',
                r'\s*\|.*$',
            ]
            for pattern in patterns_to_remove:
                clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
            
            match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', clean_title.strip())
            if match:
                if not artist:
                    artist = match.group(1).strip()
                track = match.group(2).strip()
            else:
                track = clean_title.strip()
        
        print(f"[LRCLIB] Searching: track='{track}', artist='{artist}'")
        
        headers = {'User-Agent': 'KaraokeShen/1.0'}
        search_url = f"https://lrclib.net/api/search?track_name={requests.utils.quote(track)}"
        if artist:
            search_url += f"&artist_name={requests.utils.quote(artist)}"
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            results = response.json()
            if results and len(results) > 0:
                for result in results:
                    # Prefer synced lyrics, but also accept plain
                    synced_lyrics = result.get('syncedLyrics')
                    plain_lyrics = result.get('plainLyrics')
                    
                    if synced_lyrics:
                        lyrics = lrc_to_plain_text(synced_lyrics)
                    elif plain_lyrics:
                        lyrics = plain_lyrics
                    else:
                        continue
                    
                    if lyrics and len(lyrics.split('\n')) > 3:
                        print(f"[LRCLIB] Found lyrics: {result.get('artistName')} - {result.get('trackName')}")
                        return {
                            'lyrics': lyrics,
                            'source': 'lrclib',
                            'track': result.get('trackName', track),
                            'artist': result.get('artistName', artist),
                        }
        return None
        
    except Exception as e:
        print(f"[LRCLIB ERROR] {e}")
        return None


def search_lyrics_ovh_simple(artist, track):
    """Search for lyrics from lyrics.ovh API - returns plain text."""
    try:
        if not artist or not track:
            return None
        
        print(f"[LYRICS.OVH] Searching: artist='{artist}', track='{track}'")
        
        url = f"https://api.lyrics.ovh/v1/{requests.utils.quote(artist)}/{requests.utils.quote(track)}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            lyrics = data.get('lyrics', '')
            if lyrics and len(lyrics.split('\n')) > 3:
                print(f"[LYRICS.OVH] Found lyrics")
                return {
                    'lyrics': lyrics.strip(),
                    'source': 'lyrics.ovh',
                    'track': track,
                    'artist': artist,
                }
        return None
        
    except Exception as e:
        print(f"[LYRICS.OVH ERROR] {e}")
        return None


def search_lyrics_chinese(video_title, artist='', track=''):
    """Search for Chinese lyrics using multiple sources."""
    import re
    
    # Extract song info if not provided
    if not artist or not track:
        extracted_artist, extracted_track = extract_song_info(video_title)
        if not artist:
            artist = extracted_artist
        if not track:
            track = extracted_track
    
    print(f"[CHINESE] Searching: artist='{artist}', track='{track}'")
    
    # Try NetEase Music first (most reliable for Chinese)
    result = search_lyrics_netease(artist, track)
    if result:
        return result
    
    # Try QQ Music
    result = search_lyrics_qq(artist, track)
    if result:
        return result
    
    # Try Kugou Music
    result = search_lyrics_kugou(artist, track)
    if result:
        return result
    
    # Try with just track name if artist search failed
    if artist:
        result = search_lyrics_netease('', track)
        if result:
            return result
        
        result = search_lyrics_qq('', track)
        if result:
            return result
        
        result = search_lyrics_kugou('', track)
        if result:
            return result
    
    # Try Gecimi as last resort
    try:
        search_term = f"{artist} {track}".strip() if artist else track
        gecimi_url = f"http://gecimi.com/api/lyric/{requests.utils.quote(search_term)}"
        response = requests.get(gecimi_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0 and data.get('result'):
                for item in data['result']:
                    lrc_url = item.get('lrc')
                    if lrc_url:
                        lrc_response = requests.get(lrc_url, timeout=5)
                        if lrc_response.status_code == 200:
                            captions = parse_lrc(lrc_response.text)
                            if captions:
                                return {
                                    'available': True,
                                    'source': 'gecimi',
                                    'track': item.get('song', track),
                                    'artist': item.get('artist', artist),
                                    'synced': True,
                                    'languages': ['zh'],
                                    'language': 'zh',
                                    'captions': captions
                                }
    except Exception as e:
        print(f"[GECIMI ERROR] {e}")
    
    return None


def search_lyrics_lrclib(video_title, artist='', track=''):
    """Search for synced lyrics from LRCLIB API with short timeout."""
    try:
        import re
        clean_title = video_title
        # Remove common video title patterns
        patterns_to_remove = [
            r'\s*[\(\[【「].*?(?:官方|official|mv|music video|lyric|歌詞|完整版|高音質|hd|4k|1080p).*?[\)\]】」]',
            r'\s*[\(\[【「].*?[\)\]】」]\s*$',
            r'\s*-\s*(?:official|mv|music video|lyric|歌詞).*$',
            r'\s*\|.*$',
            r'\s*\/.*$',
        ]
        for pattern in patterns_to_remove:
            clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
        clean_title = clean_title.strip()
        
        # Extract artist and track
        if not track:
            match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', clean_title)
            if match:
                if not artist:
                    artist = match.group(1).strip()
                track = match.group(2).strip()
            else:
                track = clean_title
        
        print(f"[LRCLIB] Searching: track='{track}', artist='{artist}'")
        
        headers = {'User-Agent': 'KaraokeShen/1.0'}
        
        search_url = f"https://lrclib.net/api/search?track_name={requests.utils.quote(track)}"
        if artist:
            search_url += f"&artist_name={requests.utils.quote(artist)}"
        
        # Short timeout
        response = requests.get(search_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            results = response.json()
            if results and len(results) > 0:
                for result in results:
                    synced_lyrics = result.get('syncedLyrics')
                    if synced_lyrics:
                        captions = parse_lrc(synced_lyrics)
                        if captions:
                            return {
                                'available': True,
                                'source': 'lrclib',
                                'track': result.get('trackName', track),
                                'artist': result.get('artistName', artist),
                                'languages': ['lyrics'],
                                'language': 'lyrics',
                                'captions': captions
                            }
        return None
        
    except Exception as e:
        print(f"[LRCLIB ERROR] {e}")
        return None


def search_lyrics_ovh(video_title, artist='', track=''):
    """Search for lyrics from lyrics.ovh API."""
    try:
        import re
        
        # Clean and extract artist/track
        clean_title = video_title
        patterns_to_remove = [
            r'\s*[\(\[【「].*?[\)\]】」]',
            r'\s*-\s*(?:official|mv|music video|lyric|歌詞).*$',
            r'\s*\|.*$',
        ]
        for pattern in patterns_to_remove:
            clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
        clean_title = clean_title.strip()
        
        if not track or not artist:
            match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', clean_title)
            if match:
                artist = artist or match.group(1).strip()
                track = track or match.group(2).strip()
        
        if not artist or not track:
            return None
            
        print(f"[LYRICS.OVH] Searching: artist='{artist}', track='{track}'")
        
        # lyrics.ovh API
        api_url = f"https://api.lyrics.ovh/v1/{requests.utils.quote(artist)}/{requests.utils.quote(track)}"
        response = requests.get(api_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            lyrics_text = data.get('lyrics', '')
            if lyrics_text:
                # Convert plain lyrics to timed captions (estimate timing)
                lines = [l.strip() for l in lyrics_text.split('\n') if l.strip()]
                captions = []
                for i, line in enumerate(lines):
                    captions.append({
                        'start': i * 3.5,
                        'end': (i + 1) * 3.5,
                        'text': line
                    })
                if captions:
                    return {
                        'available': True,
                        'source': 'lyrics.ovh',
                        'track': track,
                        'artist': artist,
                        'languages': ['lyrics'],
                        'language': 'lyrics',
                        'captions': captions,
                        'synced': False
                    }
        return None
        
    except Exception as e:
        print(f"[LYRICS.OVH ERROR] {e}")
        return None


def parse_lrc(lrc_content):
    """Parse LRC format lyrics into timed captions."""
    import re
    captions = []
    pattern = r'\[(\d{1,2}):(\d{2})[\.:,](\d{1,3})\]\s*(.+)'
    
    lines = lrc_content.split('\n')
    for line in lines:
        match = re.match(pattern, line.strip())
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            ms_str = match.group(3)
            if len(ms_str) == 2:
                milliseconds = int(ms_str) * 10
            else:
                milliseconds = int(ms_str)
            
            start_time = minutes * 60 + seconds + milliseconds / 1000.0
            text = match.group(4).strip()
            
            if text:
                captions.append({
                    'start': start_time,
                    'text': text
                })
    
    for i in range(len(captions)):
        if i < len(captions) - 1:
            captions[i]['end'] = captions[i + 1]['start']
        else:
            captions[i]['end'] = captions[i]['start'] + 5
    
    return captions


def get_youtube_captions(video_id, lang='zh-TW,zh-Hant,zh,zh-Hans,en,ja,ko'):
    """Get captions from YouTube as fallback."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': lang.split(','),
            'subtitlesformat': 'json3',
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            all_subs = {**automatic_captions, **subtitles}
            
            if not all_subs:
                return {'available': False, 'languages': [], 'captions': []}
            
            preferred_langs = lang.split(',')
            selected_lang = None
            selected_subs = None
            
            for pref in preferred_langs:
                if pref in all_subs:
                    selected_lang = pref
                    selected_subs = all_subs[pref]
                    break
            
            if not selected_lang and all_subs:
                selected_lang = list(all_subs.keys())[0]
                selected_subs = all_subs[selected_lang]
            
            if not selected_subs:
                return {'available': False, 'languages': list(all_subs.keys()), 'captions': []}
            
            sub_url = None
            for fmt in selected_subs:
                if fmt.get('ext') == 'json3':
                    sub_url = fmt.get('url')
                    break
            
            if not sub_url and selected_subs:
                sub_url = selected_subs[0].get('url')
            
            if not sub_url:
                return {'available': False, 'languages': list(all_subs.keys()), 'captions': []}
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            sub_response = requests.get(sub_url, headers=headers, timeout=10)
            
            if sub_response.status_code != 200:
                return {'available': False, 'error': 'Failed to fetch subtitle content'}
            
            try:
                sub_data = sub_response.json()
                captions = []
                
                for event in sub_data.get('events', []):
                    if 'segs' not in event:
                        continue
                    
                    start_ms = event.get('tStartMs', 0)
                    duration_ms = event.get('dDurationMs', 0)
                    text = ''.join(seg.get('utf8', '') for seg in event.get('segs', []))
                    text = text.strip()
                    
                    if text and text != '\n':
                        captions.append({
                            'start': start_ms / 1000.0,
                            'end': (start_ms + duration_ms) / 1000.0,
                            'text': text
                        })
                
                return {
                    'available': True,
                    'source': 'youtube',
                    'language': selected_lang,
                    'languages': list(all_subs.keys()),
                    'captions': captions
                }
                
            except Exception as parse_err:
                return {'available': False, 'error': str(parse_err)}
            
    except Exception as e:
        return {'available': False, 'error': str(e)}


@app.route('/api/upload_lrc', methods=['POST'])
def upload_lrc():
    """Upload a custom LRC file for a video."""
    video_id = request.form.get('video_id', '').strip()
    lrc_content = request.form.get('lrc_content', '')
    
    if not video_id or not lrc_content:
        return jsonify({'error': 'Missing video_id or lrc_content'}), 400
    
    try:
        captions = parse_lrc(lrc_content)
        if captions:
            return jsonify({
                'available': True,
                'source': 'upload',
                'captions': captions,
                'count': len(captions)
            })
        else:
            return jsonify({'error': 'Failed to parse LRC content'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/proxy_stream')
def proxy_stream():
    """Proxy the video stream to bypass CORS."""
    video_id = request.args.get('v')
    if not video_id:
        return "Missing video id", 400

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"--- [PROXY] Streaming: {video_id} ---")

    try:
        # Create a fresh yt-dlp instance with cookies support
        opts = {
            'format': '18/22/best[ext=mp4][vcodec^=avc1][acodec^=mp4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'noplaylist': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Select format 18 or 22 (legacy combined)
            best_f = None
            for fid in ['18', '22']:
                best_f = next((f for f in info.get('formats', []) if f.get('format_id') == fid), None)
                if best_f:
                    break

            if not best_f:
                # Fallback to any merged mp4
                for f in info.get('formats', []):
                    if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        best_f = f
                        break

            if not best_f:
                # Last resort: any format with video
                for f in info.get('formats', []):
                    if f.get('vcodec') != 'none':
                        best_f = f
                        break

            if not best_f:
                print("[PROXY ERROR] No compatible format found")
                return "No compatible format found", 404

            stream_url = best_f.get('url')
            print(f"[PROXY] Format: {best_f.get('format_id')} - {best_f.get('format_note', 'N/A')}")

            # Use requests to stream the content with proper headers
            req_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://www.youtube.com',
                'Referer': 'https://www.youtube.com/',
            }
            
            # Add range header if provided
            if request.headers.get('Range'):
                req_headers['Range'] = request.headers.get('Range')

            req = requests.get(stream_url, headers=req_headers, stream=True, timeout=30)
            
            print(f"[PROXY] Response status: {req.status_code}")

            # Build response headers
            response_headers = {
                'Content-Type': 'video/mp4',
                'Accept-Ranges': 'bytes',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache'
            }

            if 'Content-Range' in req.headers:
                response_headers['Content-Range'] = req.headers['Content-Range']
            if 'Content-Length' in req.headers:
                response_headers['Content-Length'] = req.headers['Content-Length']

            def generate():
                for chunk in req.iter_content(chunk_size=1024 * 1024):
                    yield chunk

            return Response(generate(), status=req.status_code, headers=response_headers)

    except Exception as e:
        import traceback
        print(f"[PROXY ERROR] {e}")
        traceback.print_exc()
        return str(e), 500


def main():
    """Start the Flask web server."""
    port = int(os.environ.get('PORT', 8080))
    print(f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     🎤  卡拉OK神歡唱系統 - Web Version                   ║
║                                                          ║
║     Server running at: http://localhost:{port}            ║
║     Open this URL in your browser to start!              ║
║                                                          ║
║     Press Ctrl+C to stop the server                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    main()
