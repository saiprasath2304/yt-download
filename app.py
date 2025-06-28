from flask import Flask, render_template, request, jsonify, send_file, abort
import yt_dlp
import os
import time
import random
import tempfile
import threading
from urllib.parse import urlparse, parse_qs
import re
from datetime import datetime
import shutil
import logging
import requests
from PIL import Image
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store download progress and cleanup old entries
download_progress = {}

def get_random_user_agent():
    """Get a random user agent to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
    ]
    return random.choice(user_agents)

def cleanup_old_downloads():
    """Clean up old download entries and temp files"""
    current_time = time.time()
    expired_ids = []
    
    for download_id, data in download_progress.items():
        # Remove entries older than 1 hour
        if current_time - float(download_id.split('_')[0]) > 3600:
            expired_ids.append(download_id)
            # Clean up temp files if they exist
            if 'file_path' in data and os.path.exists(data['file_path']):
                try:
                    temp_dir = os.path.dirname(data['file_path'])
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    logger.error(f"Error cleaning up temp directory: {e}")
    
    for expired_id in expired_ids:
        del download_progress[expired_id]

class ProgressHook:
    def __init__(self, download_id):
        self.download_id = download_id
    
    def __call__(self, d):
        try:
            if d['status'] == 'downloading':
                # Extract percentage safely
                percent_str = d.get('_percent_str', '0%').strip()
                speed_str = d.get('_speed_str', 'N/A')
                
                download_progress[self.download_id] = {
                    'status': 'downloading',
                    'percent': percent_str,
                    'speed': speed_str,
                    'downloaded_bytes': d.get('downloaded_bytes', 0),
                    'total_bytes': d.get('total_bytes', 0)
                }
            elif d['status'] == 'finished':
                download_progress[self.download_id] = {
                    'status': 'finished',
                    'filename': os.path.basename(d['filename']),
                    'file_path': d['filename']
                }
        except Exception as e:
            logger.error(f"Progress hook error: {e}")

def is_valid_youtube_url(url):
    """Validate YouTube URL with improved regex"""
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True
    return False

def get_video_info(url):
    """Extract video information without downloading"""
    # Try different extraction methods
    extraction_methods = [
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb', 'tv_embedded'],
                    'skip': ['dash'],
                    'player_skip': ['webpage', 'configs'],
                    'player_params': {'hl': 'en', 'gl': 'US'},
                    'player_include': ['player_response', 'player_js'],
                    'extract_flat': False,
                    'extract_info': True
                }
            }
        },
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'skip': ['dash'],
                    'player_skip': ['webpage'],
                    'player_params': {'hl': 'en', 'gl': 'US'}
                }
            }
        },
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['dash'],
                    'player_params': {'hl': 'en', 'gl': 'US'}
                }
            }
        }
    ]
    
    for i, method in enumerate(extraction_methods):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'http_headers': {
                    'User-Agent': get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                },
                'sleep_interval': 2,
                'max_sleep_interval': 5,
                'retries': 3,
                'fragment_retries': 3,
                'ignoreerrors': False,
                'no_warnings': True,
                'cookiesfrombrowser': None,
                'cookiefile': None
            }
            ydl_opts.update(method)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Get available formats for quality options
                formats = info.get('formats', [])
                available_qualities = []
                
                # Extract unique quality options
                quality_map = {}
                for fmt in formats:
                    if fmt.get('height') and fmt.get('ext') in ['mp4', 'webm']:
                        height = fmt['height']
                        if height not in quality_map:
                            quality_map[height] = {
                                'height': height,
                                'ext': fmt['ext'],
                                'filesize': fmt.get('filesize', 0),
                                'format_id': fmt['format_id']
                            }
                        # Keep the best format for each height
                        elif fmt.get('filesize', 0) > quality_map[height]['filesize']:
                            quality_map[height] = {
                                'height': height,
                                'ext': fmt['ext'],
                                'filesize': fmt.get('filesize', 0),
                                'format_id': fmt['format_id']
                            }
                
                available_qualities = sorted(quality_map.values(), key=lambda x: x['height'], reverse=True)
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', '')[:200] + '...' if info.get('description') else '',
                    'upload_date': info.get('upload_date', ''),
                    'available_qualities': available_qualities,
                    'video_id': info.get('id', '')
                }
                
        except Exception as e:
            logger.warning(f"Extraction method {i+1} failed: {str(e)}")
            if i == len(extraction_methods) - 1:  # Last method
                logger.error(f"All extraction methods failed for URL: {url}")
                return None
            continue
    
    return None

def download_thumbnail(thumbnail_url, video_id, temp_dir):
    """Download and save thumbnail"""
    try:
        headers = {
            'User-Agent': get_random_user_agent()
        }
        response = requests.get(thumbnail_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Save thumbnail
        thumbnail_path = os.path.join(temp_dir, f'{video_id}_thumbnail.jpg')
        with open(thumbnail_path, 'wb') as f:
            f.write(response.content)
        
        return thumbnail_path
    except Exception as e:
        logger.error(f"Error downloading thumbnail: {e}")
        return None

def download_video(url, quality='best', download_id=None, download_thumbnail_option=False):
    """Download video with improved error handling and progress tracking"""
    if not download_id:
        download_id = str(int(time.time()))
    
    # Create temporary directory with better naming
    temp_dir = tempfile.mkdtemp(prefix=f'ytdl_{download_id}_')
    
    # Anti-detection measures
    time.sleep(random.uniform(1, 3))
    
    # Enhanced quality mapping for better format selection
    quality_formats = {
        'best': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best',
        'high': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
        'medium': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best',
        'low': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/worst',
        'audio_only': 'bestaudio[ext=m4a]/bestaudio'
    }
    
    # Try different extraction methods
    extraction_methods = [
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb', 'tv_embedded'],
                    'skip': ['dash'],
                    'player_skip': ['webpage', 'configs'],
                    'player_params': {'hl': 'en', 'gl': 'US'},
                    'player_include': ['player_response', 'player_js'],
                    'extract_flat': False,
                    'extract_info': True
                }
            }
        },
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'skip': ['dash'],
                    'player_skip': ['webpage'],
                    'player_params': {'hl': 'en', 'gl': 'US'}
                }
            }
        },
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['dash'],
                    'player_params': {'hl': 'en', 'gl': 'US'}
                }
            }
        }
    ]
    
    for i, method in enumerate(extraction_methods):
        try:
            ydl_opts = {
                'format': quality_formats.get(quality, 'best'),
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'http_headers': {
                    'User-Agent': get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                },
                'sleep_interval': 2,
                'max_sleep_interval': 5,
                'retries': 3,
                'fragment_retries': 3,
                'ignoreerrors': False,
                'no_warnings': True,
                'progress_hooks': [ProgressHook(download_id)],
                'writesubtitles': False,
                'writeautomaticsub': False,
                'writethumbnail': download_thumbnail_option,
                'merge_output_format': 'mp4',
                'cookiesfrombrowser': None,
                'cookiefile': None,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }] if quality != 'audio_only' else []
            }
            ydl_opts.update(method)
            
            # First get video info to extract thumbnail if requested
            video_info = get_video_info(url)
            thumbnail_path = None
            
            if download_thumbnail_option and video_info and video_info.get('thumbnail'):
                thumbnail_path = download_thumbnail(
                    video_info['thumbnail'], 
                    video_info.get('video_id', download_id), 
                    temp_dir
                )
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                download_progress[download_id] = {'status': 'starting', 'percent': '0%'}
                ydl.download([url])
                
                # Find the downloaded file
                files = [f for f in os.listdir(temp_dir) if not f.startswith('.')]
                if files:
                    file_path = os.path.join(temp_dir, files[0])
                    # Update progress with file path and thumbnail path
                    if download_id in download_progress:
                        download_progress[download_id]['file_path'] = file_path
                        if thumbnail_path:
                            download_progress[download_id]['thumbnail_path'] = thumbnail_path
                    return file_path
                else:
                    raise Exception("No file was downloaded")
                    
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Sign in to confirm you're not a bot" in error_msg:
                error_msg = "YouTube is blocking requests. Please try again later."
            elif "Video unavailable" in error_msg:
                error_msg = "This video is not available for download."
            elif "Failed to extract any player response" in error_msg:
                logger.warning(f"Player response extraction failed with method {i+1}: {error_msg}")
                if i == len(extraction_methods) - 1:  # Last method
                    error_msg = "Unable to extract video information. YouTube may have changed their API."
                    download_progress[download_id] = {'status': 'error', 'message': error_msg}
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise Exception(error_msg)
                continue  # Try next method
            else:
                download_progress[download_id] = {'status': 'error', 'message': error_msg}
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise Exception(error_msg)
        except Exception as e:
            logger.warning(f"Download method {i+1} failed: {str(e)}")
            if i == len(extraction_methods) - 1:  # Last method
                error_msg = f"Download failed: {str(e)}"
                download_progress[download_id] = {'status': 'error', 'message': error_msg}
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise Exception(error_msg)
            continue  # Try next method
    
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def get_video_info_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Invalid YouTube URL. Please enter a valid YouTube video URL.'}), 400
        
        video_info = get_video_info(url)
        
        if not video_info:
            return jsonify({'error': 'Could not fetch video information. The video might be private, restricted, or YouTube is blocking requests. Please try again later.'}), 400
        
        return jsonify(video_info)
        
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg:
            error_msg = "YouTube is blocking requests. Please try again later or try a different video."
        elif "Video unavailable" in error_msg:
            error_msg = "This video is not available for download (private, restricted, or removed)."
        elif "Video is private" in error_msg:
            error_msg = "This video is private and cannot be downloaded."
        elif "This video is not available" in error_msg:
            error_msg = "This video is not available in your region or has been removed."
        elif "Failed to extract any player response" in error_msg:
            error_msg = "Unable to extract video information. YouTube may have changed their API. Please try again later."
        else:
            error_msg = f"Error fetching video info: {error_msg}"
        
        logger.error(f"Error in get_video_info_api: {error_msg}")
        return jsonify({'error': error_msg}), 400

@app.route('/api/download', methods=['POST'])
def download_video_api():
    try:
        # Clean up old downloads first
        cleanup_old_downloads()
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        url = data.get('url', '').strip()
        quality = data.get('quality', 'best')
        download_thumbnail_option = data.get('download_thumbnail', False)
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Generate unique download ID
        download_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Start download in background thread
        def background_download():
            try:
                file_path = download_video(url, quality, download_id, download_thumbnail_option)
                if download_id in download_progress:
                    download_progress[download_id]['file_path'] = file_path
            except Exception as e:
                logger.error(f"Background download error: {e}")
                download_progress[download_id] = {
                    'status': 'error', 
                    'message': str(e)
                }
        
        thread = threading.Thread(target=background_download)
        thread.daemon = True
        thread.start()
        
        return jsonify({'download_id': download_id})
    
    except Exception as e:
        logger.error(f"Download API error: {e}")
        return jsonify({'error': 'An error occurred while starting the download.'}), 500

@app.route('/api/download-thumbnail', methods=['POST'])
def download_thumbnail_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Get video info first
        video_info = get_video_info(url)
        if not video_info or not video_info.get('thumbnail'):
            return jsonify({'error': 'Could not extract thumbnail information.'}), 400
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f'thumbnail_{int(time.time())}_')
        
        # Download thumbnail
        thumbnail_path = download_thumbnail(
            video_info['thumbnail'], 
            video_info.get('video_id', 'thumbnail'), 
            temp_dir
        )
        
        if not thumbnail_path:
            return jsonify({'error': 'Failed to download thumbnail.'}), 500
        
        # Return thumbnail file
        filename = f"{video_info.get('video_id', 'thumbnail')}_thumbnail.jpg"
        
        # Schedule cleanup after download
        def cleanup_after_download():
            time.sleep(10)  # Wait 10 seconds
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"Thumbnail cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_after_download)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        return send_file(thumbnail_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        logger.error(f"Thumbnail download API error: {e}")
        return jsonify({'error': 'An error occurred while downloading the thumbnail.'}), 500

@app.route('/api/progress/<download_id>')
def get_progress(download_id):
    try:
        progress = download_progress.get(download_id, {'status': 'not_found'})
        return jsonify(progress)
    except Exception as e:
        logger.error(f"Progress API error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to get progress'}), 500

@app.route('/api/download-file/<download_id>')
def download_file(download_id):
    try:
        progress = download_progress.get(download_id)
        
        if not progress or progress.get('status') != 'finished':
            abort(404)
        
        file_path = progress.get('file_path')
        if not file_path or not os.path.exists(file_path):
            abort(404)
        
        filename = os.path.basename(file_path)
        
        # Schedule cleanup after download
        def cleanup_after_download():
            time.sleep(10)  # Wait 10 seconds
            try:
                temp_dir = os.path.dirname(file_path)
                shutil.rmtree(temp_dir, ignore_errors=True)
                if download_id in download_progress:
                    del download_progress[download_id]
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_after_download)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        return send_file(file_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        logger.error(f"Download file error: {e}")
        abort(500)

# Template filters
@app.template_filter('format_duration')
def format_duration(seconds):
    if not seconds:
        return "Unknown"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

@app.template_filter('format_views')
def format_views(views):
    if not views:
        return "Unknown"
    
    if views >= 1000000000:
        return f"{views/1000000000:.1f}B"
    elif views >= 1000000:
        return f"{views/1000000:.1f}M"
    elif views >= 1000:
        return f"{views/1000:.1f}K"
    else:
        return str(views)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # For production, use gunicorn or similar WSGI server
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=True)
