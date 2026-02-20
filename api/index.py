from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import requests
import os
import json
import re

app = Flask(__name__)
CORS(app)

# ============================================
# Helper Functions
# ============================================

def extract_song_info(video_title):
    """Extract artist and track from video title."""
    clean_title = video_title
    
    patterns_to_remove = [
        r'\s*[\(\[【「].*?(?:官方|official|mv|music video|lyric|歌詞|完整版|高音質|hd|4k|1080p|live|現場|演唱會).*?[\)\]】」]',
        r'\s*[\(\[【「].*?[\)\]】」]',
        r'\s*[-–—]\s*(?:official|mv|music video|lyric|歌詞).*$',
        r'\s*\|.*$',
        r'\s*Official\s*(?:Music\s*)?(?:Video)?$',
    ]
    for pattern in patterns_to_remove:
        clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
    clean_title = clean_title.strip()
    
    # Pattern 1: Artist《Song》or Artist「Song」
    match = re.match(r'^(.+?)\s*[《「](.+?)[》」]\s*$', clean_title)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    
    # Pattern 2: Artist - Song
    match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', clean_title)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    
    return '', clean_title


def contains_chinese(text):
    """Check if text contains Chinese characters."""
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


def lrc_to_plain_text(lrc_content):
    """Convert LRC format to plain text by removing timestamps."""
    lines = []
    for line in lrc_content.split('\n'):
        text = re.sub(r'\[\d{1,2}:\d{2}[\.:,]?\d{0,3}\]', '', line).strip()
        if text and not re.match(r'^\[.*\]$', line.strip()):
            lines.append(text)
    return '\n'.join(lines)


# ============================================
# Lyrics Search Functions
# ============================================

def search_lyrics_lrclib(artist, track):
    """Search LRCLIB for lyrics."""
    try:
        headers = {'User-Agent': 'KaraokeShen/1.0'}
        search_url = f"https://lrclib.net/api/search?track_name={requests.utils.quote(track)}"
        if artist:
            search_url += f"&artist_name={requests.utils.quote(artist)}"
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            results = response.json()
            if results and len(results) > 0:
                for result in results:
                    synced = result.get('syncedLyrics')
                    plain = result.get('plainLyrics')
                    
                    lyrics = lrc_to_plain_text(synced) if synced else plain
                    
                    if lyrics and len(lyrics.split('\n')) > 3:
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


def search_lyrics_genius(artist, track):
    """Search Genius for lyrics."""
    try:
        if not track:
            return None
        
        search_term = f"{artist} {track}".strip() if artist else track
        
        search_url = "https://genius.com/api/search/multi"
        params = {'q': search_term}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        sections = data.get('response', {}).get('sections', [])
        
        for section in sections:
            if section.get('type') == 'song':
                hits = section.get('hits', [])
                if hits:
                    song = hits[0].get('result', {})
                    song_url = song.get('url', '')
                    
                    if song_url:
                        # Fetch lyrics from page
                        page_response = requests.get(song_url, headers=headers, timeout=10)
                        if page_response.status_code == 200:
                            html = page_response.text
                            
                            # Extract lyrics
                            lyrics_parts = []
                            pattern = r'<div[^>]*class="[^"]*Lyrics__Container[^"]*"[^>]*>(.*?)</div>'
                            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
                            
                            for match in matches:
                                text = re.sub(r'<br\s*/?>', '\n', match)
                                text = re.sub(r'<[^>]+>', '', text)
                                text = text.strip()
                                if text:
                                    lyrics_parts.append(text)
                            
                            if lyrics_parts:
                                return {
                                    'lyrics': '\n\n'.join(lyrics_parts),
                                    'source': 'genius',
                                    'track': song.get('title', track),
                                    'artist': song.get('primary_artist', {}).get('name', artist),
                                }
        return None
    except Exception as e:
        print(f"[GENIUS ERROR] {e}")
        return None


def search_lyrics_ovh(artist, track):
    """Search lyrics.ovh for lyrics."""
    try:
        if not artist or not track:
            return None
        
        url = f"https://api.lyrics.ovh/v1/{requests.utils.quote(artist)}/{requests.utils.quote(track)}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            lyrics = data.get('lyrics', '')
            if lyrics and len(lyrics.split('\n')) > 3:
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


def fetch_lyrics(artist, track, video_title):
    """Fetch lyrics from multiple sources."""
    # Try LRCLIB
    result = search_lyrics_lrclib(artist, track)
    if result:
        return result
    
    # Try Genius
    result = search_lyrics_genius(artist, track)
    if result:
        return result
    
    # Try lyrics.ovh
    result = search_lyrics_ovh(artist, track)
    if result:
        return result
    
    # Try with just track name
    if artist:
        result = search_lyrics_lrclib('', track)
        if result:
            return result
        result = search_lyrics_genius('', track)
        if result:
            return result
    
    return None


# ============================================
# API Routes
# ============================================

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'message': 'Karaoke Shen API is running'})


@app.route('/api/subtitles')
def get_subtitles():
    """Get lyrics for a video."""
    video_id = request.args.get('id', '').strip()
    video_title = request.args.get('title', '').strip()
    
    if not video_id:
        return jsonify({'error': 'Missing video ID'}), 400
    
    try:
        # Extract song info from title
        artist, track = extract_song_info(video_title) if video_title else ('', '')
        
        # Fetch lyrics
        result = fetch_lyrics(artist, track, video_title)
        
        if result:
            return jsonify({
                'available': True,
                'lyrics': result['lyrics'],
                'artist': result.get('artist', artist),
                'track': result.get('track', track),
                'source': result['source']
            })
        
        return jsonify({
            'available': False,
            'lyrics': '',
            'artist': artist,
            'track': track,
            'source': 'none'
        })
        
    except Exception as e:
        print(f"[LYRICS ERROR] {e}")
        return jsonify({'available': False, 'error': str(e)})


@app.route('/api/search')
def search():
    """Search YouTube - Note: This won't work on Vercel due to yt-dlp limitations."""
    return jsonify({
        'error': 'YouTube search is not available on Vercel deployment. Please use the local server for full functionality.',
        'message': 'For karaoke features, run the app locally with: python3 server.py'
    }), 501


@app.route('/api/stream_url')
def stream_url():
    """Get stream URL - Note: This won't work on Vercel."""
    return jsonify({
        'error': 'Video streaming is not available on Vercel deployment.',
        'message': 'For video playback, run the app locally with: python3 server.py'
    }), 501


# Vercel serverless handler
def handler(request):
    return app(request)


if __name__ == '__main__':
    app.run(debug=True)
