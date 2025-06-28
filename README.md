# requirements.txt
Flask==2.3.3
yt-dlp>=2023.12.30
gunicorn==21.2.0
Werkzeug==2.3.7

# Procfile (for Heroku/Railway)
web: gunicorn app:app

# runtime.txt (specify Python version)
python-3.11.5

# .gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/
.spyderproject
.spyproject
.rope_project
/.vscode
.idea/
*.swp
*.swo
*~

# Docker files
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create templates directory
RUN mkdir -p templates

# Expose port
EXPOSE 5000

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

# docker-compose.yml
version: '3.8'
services:
  youtube-downloader:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - PORT=5000
    volumes:
      - /tmp:/tmp
    restart: unless-stopped

# railway.toml (for Railway deployment)
[build]
builder = "nixpacks"

[deploy]
startCommand = "gunicorn app:app"
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 10

# render.yaml (for Render deployment)
services:
  - type: web
    name: youtube-downloader
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn app:app"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.5
      - key: FLASK_ENV
        value: production

# YouTube Downloader Pro

A high-quality YouTube video downloader with thumbnail support, built with Flask and yt-dlp.

## ✨ Features

- **High-Quality Downloads**: Download videos in up to 1080p quality
- **Thumbnail Downloads**: Download video thumbnails separately or with videos
- **Multiple Quality Options**: Choose from best, high, medium, low, or audio-only
- **Real-time Progress**: Track download progress with speed and percentage
- **Modern UI**: Beautiful, responsive interface with dark theme
- **No Ads**: Clean, ad-free experience
- **Secure**: No malware, just clean downloads

## 🚀 Quick Start

### Prerequisites

- Python 3.7+
- FFmpeg (for video processing)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd yt-downloader
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and go to `http://localhost:5000`

## 📦 Docker Deployment

### Using Docker Compose

1. Build and run with Docker Compose:
```bash
docker-compose up --build
```

2. Access the application at `http://localhost:5000`

### Manual Docker Build

1. Build the Docker image:
```bash
docker build -t youtube-downloader .
```

2. Run the container:
```bash
docker run -p 5000:5000 youtube-downloader
```

## 🎯 Usage

1. **Enter YouTube URL**: Paste any YouTube video URL in the input field
2. **Get Video Info**: Click "Get Info" to fetch video details and available qualities
3. **Choose Quality**: Select your preferred video quality from the available options
4. **Download Options**: Choose whether to include thumbnail with the video
5. **Start Download**: Click "Start Download" and monitor progress
6. **Download Thumbnail**: Use the "Download Thumbnail" button to get just the thumbnail

## 🔧 API Endpoints

### Get Video Information
```http
POST /api/video-info
Content-Type: application/json

{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

### Start Video Download
```http
POST /api/download
Content-Type: application/json

{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "quality": "best",
    "download_thumbnail": true
}
```

### Download Thumbnail Only
```http
POST /api/download-thumbnail
Content-Type: application/json

{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

### Get Download Progress
```http
GET /api/progress/{download_id}
```

### Download Completed File
```http
GET /api/download-file/{download_id}
```

## 🎨 Quality Options

- **Best**: Up to 1080p with best video and audio quality
- **High**: Up to 720p with good quality
- **Medium**: Up to 480p with balanced quality and size
- **Low**: Up to 360p for smaller file sizes
- **Audio Only**: MP3/M4A audio files only

## 🛠️ Configuration

### Environment Variables

- `PORT`: Server port (default: 5000)
- `DEBUG`: Enable debug mode (default: False)
- `MAX_CONTENT_LENGTH`: Maximum file size in bytes (default: 500MB)

### Quality Settings

You can customize quality formats in `app.py`:

```python
quality_formats = {
    'best': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best',
    'high': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
    'medium': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best',
    'low': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/worst',
    'audio_only': 'bestaudio[ext=m4a]/bestaudio'
}
```

## 🧪 Testing

Run the test suite to verify functionality:

```bash
python test/test_downloader.py
```

## 📁 Project Structure

```
yt-downloader/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
├── templates/
│   └── index.html        # Frontend interface
├── test/
│   └── test_downloader.py # Test suite
└── README.md             # This file
```

## 🔒 Security Features

- Input validation for YouTube URLs
- Temporary file cleanup
- Rate limiting and anti-detection measures
- Secure file handling

## 🌟 Advanced Features

### Thumbnail Downloads
- Download thumbnails separately from videos
- High-quality thumbnail extraction
- Automatic cleanup after download

### Progress Tracking
- Real-time download progress
- Speed and percentage display
- Error handling and recovery

### Quality Selection
- Dynamic quality detection
- File size estimation
- Format optimization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is for personal use only. Please respect YouTube's terms of service.

## ⚠️ Disclaimer

This tool is for educational purposes and personal use only. Users are responsible for complying with YouTube's terms of service and applicable laws. The developers are not responsible for any misuse of this software.

## 🆘 Troubleshooting

### Common Issues

1. **Download fails**: Check your internet connection and try again
2. **Quality not available**: Some videos may not have all quality options
3. **Thumbnail download fails**: The video might be private or restricted

### Performance Tips

- Use lower quality settings for faster downloads
- Close other applications to free up bandwidth
- Use a stable internet connection

## 📞 Support

If you encounter any issues or have questions, please open an issue on the repository.
