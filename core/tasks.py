import os
import datetime
import time
import shutil
import yt_dlp
from celery import shared_task
from django.conf import settings
from .models import DownloadTask

BASE_DIR = settings.BASE_DIR
# Thư mục bin cục bộ (cho Windows)
LOCAL_BIN_DIR = os.path.join(BASE_DIR, 'bin')
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')
DOWNLOAD_DIR = os.path.join(settings.MEDIA_ROOT, 'downloads')

# --- HÀM HỖ TRỢ TÌM KIẾM TOOL (CROSS-PLATFORM) ---
def get_binary_path(name):
    """
    Tìm đường dẫn file thực thi (ffmpeg, aria2c)
    Ưu tiên tìm trong System Path (Linux/Docker) trước, sau đó mới tìm trong folder bin (Windows)
    """
    # 1. Tìm trong môi trường hệ thống (Linux/Docker)
    path = shutil.which(name)
    if path:
        return path
    
    # 2. Tìm trong thư mục bin của dự án (Windows dev)
    # Lưu ý: Windows cần đuôi .exe
    exe_name = f"{name}.exe"
    local_path = os.path.join(LOCAL_BIN_DIR, exe_name)
    if os.path.exists(local_path):
        return local_path
    
    return None

# Tìm đường dẫn ngay khi load file
FFMPEG_PATH = get_binary_path('ffmpeg')
# Trên Linux lệnh thường là 'aria2c', trên Windows là 'aria2c.exe'
ARIA2C_PATH = get_binary_path('aria2c')

@shared_task(bind=True)
def process_download_task(self, db_task_id):
    # [DEBUG TIME]
    print(f"🕒 SYSTEM TIME: {datetime.datetime.now()}")
    print(f"🔧 TOOL PATHS: FFmpeg={FFMPEG_PATH}, Aria2c={ARIA2C_PATH}")

    try:
        task_db = DownloadTask.objects.get(id=db_task_id)
    except DownloadTask.DoesNotExist:
        return "Task not found"

    # [CLEAN URL]
    original_url = task_db.url
    if 'threads.com' in original_url: 
        original_url = original_url.replace('threads.com', 'threads.net')
    
    if '?' in original_url: 
        task_db.url = original_url.split('?')[0]
    else:
        task_db.url = original_url

    task_db.status = 'DOWNLOADING'
    task_db.save()

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                p = d.get('_percent_str', '0%').replace('%', '')
                task_db.progress = float(p)
                task_db.save(update_fields=['progress'])
            except: pass
        elif d['status'] == 'finished':
            task_db.status = 'PROCESSING'
            task_db.progress = 98.0
            task_db.save()

    path_template = os.path.join(DOWNLOAD_DIR, '%(title).200s [%(id)s].%(ext)s')

    # [CẤU HÌNH YT-DLP]
    opts = {
        'outtmpl': path_template,
        # Sử dụng đường dẫn tìm được (nếu có)
        'ffmpeg_location': os.path.dirname(FFMPEG_PATH) if FFMPEG_PATH else None,
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        'quiet': False,
        'no_warnings': True,
        'ignoreerrors': True,
        'progress_hooks': [progress_hook],
        'overwrites': True,
        'force_overwrite': True,
        'no_continue': True,
        
        # HTTP HEADERS
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.threads.net/',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        },

        'writethumbnail': task_db.use_thumbnail,
        'writesubtitles': task_db.use_subtitle,
        'embedthumbnail': task_db.use_thumbnail,
        'embedsubtitles': task_db.use_subtitle,
        'subtitleslangs': ['vi', 'en', 'en-US', 'all'] if task_db.use_subtitle else None,
        'retries': 10,
    }

    # Cấu hình Aria2c (Chỉ bật nếu tìm thấy tool và không phải Threads/Insta)
    if ARIA2C_PATH and 'threads.net' not in task_db.url and 'instagram.com' not in task_db.url:
        opts['external_downloader'] = {'default': ARIA2C_PATH}
        opts['external_downloader_args'] = {'aria2c': ['-x', '16', '-k', '1M', '-s', '16']}
    
    # Logic Audio/Video
    if task_db.task_type == 'audio':
        bitrate = '320' if task_db.audio_quality == 'best' else '128'
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': task_db.audio_format, 'preferredquality': bitrate},
                {'key': 'EmbedThumbnail'}, 
                {'key': 'FFmpegMetadata'},
            ],
            'writethumbnail': True,
        })
    else:
        res = task_db.resolution
        container = task_db.container
        fmt_str = f"bestvideo[height<={res}][ext={container}]+bestaudio/best[height<={res}][ext={container}]/best"
        
        opts.update({
            'format': fmt_str,
            'merge_output_format': container,
            'subtitlesformat': 'srt' if container == 'mp4' else 'ass/srt/best',
        })
        if container == 'mp4':
            opts['postprocessor_args'] = {'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac']}
        if 'youtube' in task_db.url:
            opts['sponsorblock_remove'] = ['sponsor', 'intro', 'outro', 'selfpromo']

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            print(f"🔗 Processing: {task_db.url}")
            
            info = ydl.extract_info(task_db.url, download=True)
            
            # Retry logic nếu lần đầu thất bại (thử bỏ cookie)
            if not info:
                print("⚠️ Cookie failed, trying without cookie...")
                opts['cookiefile'] = None 
                with yt_dlp.YoutubeDL(opts) as ydl_retry:
                    info = ydl_retry.extract_info(task_db.url, download=True)
            
            if not info:
                 raise Exception("Thất bại toàn tập. Kiểm tra lại Cookie & Thời gian hệ thống!")

            if 'requested_downloads' in info:
                final_file = info['requested_downloads'][0]['filepath']
            else:
                final_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(final_file)
                if task_db.task_type == 'audio': 
                    final_file = f"{base}.{task_db.audio_format}"
                elif task_db.container == 'mp4' and not final_file.endswith('.mp4'):
                    final_file = f"{base}.mp4"

            task_db.filename = os.path.basename(final_file)
            task_db.status = 'FINISHED'
            task_db.progress = 100.0
            task_db.save()

    except Exception as e:
        task_db.status = 'FAILED'
        task_db.save()
        print(f"❌ ERROR: {str(e)}")


# --- TASK DỌN DẸP FILE RÁC (Chạy định kỳ bởi Celery Beat) ---
@shared_task
def clean_expired_files():
    """
    Dọn dẹp các file cũ hơn 1 tiếng đồng hồ để giải phóng ổ cứng.
    """
    print("🧹 STARTING CLEANUP TASK...")
    now = time.time()
    expiration_time = 3600  # 3600 giây = 1 tiếng
    
    # Duyệt thư mục downloads
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            
            # Kiểm tra xem có phải file không
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                
                if file_age > expiration_time:
                    try:
                        os.remove(filepath)
                        print(f"✅ Deleted old file: {filename}")
                    except Exception as e:
                        print(f"❌ Cannot delete {filename}: {e}")
    
    return "Cleanup Completed"