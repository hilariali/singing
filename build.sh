#!/usr/bin/env bash
# Build script for Render deployment

# Install FFmpeg for yt-dlp video extraction
apt-get update && apt-get install -y ffmpeg

# Install Python dependencies
pip install -r requirements.txt
