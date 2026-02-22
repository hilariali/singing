FROM python:3.11-slim

# Install FFmpeg for yt-dlp
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Create data directory for SQLite
RUN mkdir -p /data

# Expose port
EXPOSE 8080

# Environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Run with gunicorn
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120"]
