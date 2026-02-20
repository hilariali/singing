# 🎤 卡拉OK神歡唱系統 (Karaoke Shen)

A web-based karaoke system with YouTube video streaming and lyrics display.

## Features

- 🔍 Search YouTube for karaoke videos
- 🎵 Stream videos directly in browser
- 📝 Auto-fetch lyrics from multiple sources (LRCLIB, Genius, lyrics.ovh, NetEase)
- 💾 Database caching for fast lyrics loading
- ✏️ Manual lyrics editor
- 🎤 Karaoke mode with voice removal (mono audio center-channel cancellation)

## Local Setup (Recommended)

For full functionality, run locally:

```bash
# Install dependencies
pip3 install flask flask-cors yt-dlp requests

# Run the server
python3 server.py
```

Then open http://localhost:8080

## Vercel Deployment

⚠️ **Limited functionality on Vercel:**
- ✅ Lyrics search works
- ❌ YouTube search doesn't work (yt-dlp not available)
- ❌ Video streaming doesn't work (requires persistent server)

The Vercel deployment only supports the lyrics API. For full karaoke functionality, run locally.

### Deploy to Vercel

1. Push to GitHub
2. Import project in Vercel
3. Deploy (auto-detected from vercel.json)

## API Endpoints

- `GET /api/search?q=<query>` - Search YouTube (local only)
- `GET /api/stream_url?id=<videoId>` - Get stream URL (local only)
- `GET /api/subtitles?id=<videoId>&title=<title>` - Get lyrics
- `POST /api/save_lyrics` - Save manual lyrics

## Tech Stack

- Backend: Flask + yt-dlp
- Frontend: Vanilla JS
- Database: SQLite (local caching)
- Lyrics APIs: LRCLIB, Genius, lyrics.ovh, NetEase, Kugou

## License

MIT
