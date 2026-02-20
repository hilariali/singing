import eel
import yt_dlp
import os
import sys
import requests
from bottle import response, request

# Configure yt-dlp
# Search needs to be fast and metadata-focused
SEARCH_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
}

# Streaming needs to be strictly compatible with browser
# Without ffmpeg, we MUST use pre-merged legacy formats (18=360p, 22=720p)
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

@eel.expose
def search_youtube(query):
    """Search for videos on YouTube using keywords."""
    print(f"Searching for: {query}")
    try:
        with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
            # Get more results to increase chance of finding playable ones
            search_results = ydl.extract_info(f"ytsearch20:{query}", download=False)
            if not search_results:
                print("No results found or search failed.")
                return []
            
            results = []
            entries = search_results.get('entries', [])
            print(f"Found {len(entries)} entries.")
            
            for entry in entries:
                if entry:
                    # Robust thumbnail selection
                    thumb = entry.get('thumbnail')
                    if not thumb and entry.get('thumbnails'):
                        # Try to get high quality thumbnail
                        thumb = entry.get('thumbnails')[-1].get('url')
                        
                    results.append({
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'thumbnail': thumb,
                        'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                    })
            return results
    except Exception as e:
        import traceback
        print(f"Search error details: {e}")
        traceback.print_exc()
        return []

@eel.expose
def get_video_info(url):
    """Get info for a single video from a direct URL."""
    print(f"Getting info for URL: {url}")
    try:
        with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                print("Failed to get video info.")
                return None
            
            thumb = info.get('thumbnail')
            if not thumb and info.get('thumbnails'):
                thumb = info.get('thumbnails')[-1].get('url')

            return {
                'id': info.get('id'),
                'title': info.get('title'),
                'thumbnail': thumb,
                'url': url
            }
    except Exception as e:
        print(f"Info error details: {e}")
        return None

@eel.expose
def get_stream_url(video_id):
    """Get the local proxy URL for a YouTube video."""
    # We return a local URL that our proxy will handle
    # This bypasses CORS and referer issues
    return f"http://localhost:8000/proxy_stream?v={video_id}"

@eel.btl.route('/proxy_stream')
def proxy_stream():
    video_id = request.query.get('v')
    if not video_id:
        return "Missing video id"
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"--- [PROXY] Streaming: {video_id} ---")
    
    try:
        with yt_dlp.YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Select format 18 or 22 (legacy combined)
            best_f = None
            for fid in ['18', '22']:
                best_f = next((f for f in info.get('formats', []) if f.get('format_id') == fid), None)
                if best_f: break
            
            if not best_f:
                # Fallback to any merged mp4
                for f in info.get('formats', []):
                    if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        best_f = f
                        break
            
            if not best_f:
                return "No compatible format found"
            
            stream_url = best_f.get('url')
            
            # Use requests to stream the content
            headers = {
                'User-Agent': STREAM_OPTS['user_agent'],
                'Range': request.headers.get('Range', 'bytes=0-')
            }
            
            req = requests.get(stream_url, headers=headers, stream=True)
            
            # Set response headers
            response.set_header('Content-Type', 'video/mp4')
            response.set_header('Accept-Ranges', 'bytes')
            response.set_header('Access-Control-Allow-Origin', '*')
            
            # Relay the status code (crucial for 206 Partial Content during seeking)
            response.status = req.status_code
            
            if 'Content-Range' in req.headers:
                response.set_header('Content-Range', req.headers['Content-Range'])
            if 'Content-Length' in req.headers:
                response.set_header('Content-Length', req.headers['Content-Length'])
            
            # Return the generator to stream data
            return req.iter_content(chunk_size=1024*1024)
            
    except Exception as e:
        print(f"[PROXY ERROR] {e}")
        return str(e)

def main():
    # Find the directory where main.py is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(base_dir, 'web')
    
    # Initialize Eel with the 'web' directory
    print(f"Initializing Eel with web directory: {web_dir}")
    eel.init(web_dir)
    
    # Try to start the app
    try:
        print("Starting Shen Karaoke...")
        eel.start('index.html', size=(1200, 900), mode='chrome')
    except (SystemExit, KeyboardInterrupt):
        print("Closing application...")
    except Exception as e:
        print(f"Error starting Eel: {e}")

if __name__ == "__main__":
    main()
