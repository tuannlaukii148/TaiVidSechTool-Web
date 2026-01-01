import os
import datetime
import time
import shutil
import yt_dlp
from celery import shared_task
from django.conf import settings
from .models import DownloadTask

BASE_DIR = settings.BASE_DIR
# Thư mục chứa các file thực thi (cho Windows)
LOCAL_BIN_DIR = os.path.join(BASE_DIR, 'bin')
# File Cookie (Quan trọng để bypass Youtube)
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')
# Thư mục lưu file tải về
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

# Tìm đường dẫn ngay khi load file để tối ưu hiệu năng
FFMPEG_PATH = get_binary_path('ffmpeg')
ARIA2C_PATH = get_binary_path('aria2c')

@shared_task(bind=True)
def process_download_task(self, db_task_id):
    # [LOGGING] Ghi log để debug nếu cần
    print(f"🕒 START TASK ID: {db_task_id} | TIME: {datetime.datetime.now()}")
    print(f"🔧 TOOLS: FFmpeg={'FOUND' if FFMPEG_PATH else 'MISSING'} | Aria2c={'FOUND' if ARIA2C_PATH else 'MISSING'}")
    print(f"🍪 COOKIE FILE: {'FOUND' if os.path.exists(COOKIES_FILE) else 'MISSING (Youtube may fail)'}")

    try:
        task_db = DownloadTask.objects.get(id=db_task_id)
    except DownloadTask.DoesNotExist:
        return "Task not found"

    # [XỬ LÝ URL THREADS/INSTAGRAM]
    original_url = task_db.url
    if 'threads.com' in original_url: 
        original_url = original_url.replace('threads.com', 'threads.net')
    
    # Cắt bỏ các tham số tracking (?si=...) để URL sạch đẹp
    if '?' in original_url: 
        task_db.url = original_url.split('?')[0]
    else:
        task_db.url = original_url

    # Cập nhật trạng thái: Đang tải
    task_db.status = 'DOWNLOADING'
    task_db.save()

    # Tạo thư mục nếu chưa có
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    # Hàm cập nhật tiến trình (Hook)
    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                # Lấy % tải về và cập nhật vào DB
                p = d.get('_percent_str', '0%').replace('%', '')
                task_db.progress = float(p)
                task_db.save(update_fields=['progress'])
            except: pass
        elif d['status'] == 'finished':
            task_db.status = 'PROCESSING'
            task_db.progress = 99.0
            task_db.save()

    # Định dạng tên file lưu trên ổ cứng (Giữ nguyên tên gốc + ID để tránh trùng)
    path_template = os.path.join(DOWNLOAD_DIR, '%(title).200s [%(id)s].%(ext)s')

    # [CẤU HÌNH YT-DLP CORE]
    opts = {
        'outtmpl': path_template,
        'ffmpeg_location': os.path.dirname(FFMPEG_PATH) if FFMPEG_PATH else None,
        
        # === CHÌA KHÓA VÀNG: COOKIE ===
        # Tự động nạp cookie nếu file tồn tại
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        # ==============================

        'quiet': False, # Bật log để xem lỗi trên Render
        'no_warnings': True,
        'ignoreerrors': True,
        'progress_hooks': [progress_hook],
        'overwrites': True,       # Ghi đè file cũ
        'force_overwrite': True,
        'no_continue': True,      # Không resume (để tránh lỗi file corrupt)
        
        # Bypass SSL Errors (Fix lỗi Youtube hay gặp trên Cloud)
        'nocheckcertificate': True, 
        
        # Giả lập trình duyệt (Quan trọng cho Threads/Facebook)
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
        },

        # Cấu hình phụ đề/thumbnail
        'writethumbnail': task_db.use_thumbnail,
        'writesubtitles': task_db.use_subtitle,
        'embedthumbnail': task_db.use_thumbnail,
        'embedsubtitles': task_db.use_subtitle,
        'subtitleslangs': ['vi', 'en', 'en-US', 'all'] if task_db.use_subtitle else None,
        
        # Tự động thử lại 10 lần nếu mạng lag
        'retries': 10,
        'fragment_retries': 10,
    }

    # [CẤU HÌNH ARIA2C - TĂNG TỐC ĐỘ TẢI]
    # Chỉ bật Aria2c nếu không phải Threads/Instagram (vì bọn này chặn đa luồng)
    if ARIA2C_PATH and 'threads.net' not in task_db.url and 'instagram.com' not in task_db.url:
        opts['external_downloader'] = {'default': ARIA2C_PATH}
        opts['external_downloader_args'] = {'aria2c': ['-x', '16', '-k', '1M', '-s', '16']}
    
    # [LOGIC XỬ LÝ FORMAT (VIDEO vs AUDIO)]
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
        # Xử lý Video
        res = task_db.resolution
        container = task_db.container
        # Logic chọn chất lượng thông minh
        fmt_str = f"bestvideo[height<={res}][ext={container}]+bestaudio/best[height<={res}][ext={container}]/best"
        
        opts.update({
            'format': fmt_str,
            'merge_output_format': container,
            # Nếu là MP4 thì dùng Subtitle dạng SRT (tương thích cao)
            'subtitlesformat': 'srt' if container == 'mp4' else 'ass/srt/best',
        })
        
        # Nếu container là MP4, ép FFmpeg convert audio sang AAC để chạy được trên iPhone/Windows
        if container == 'mp4':
            opts['postprocessor_args'] = {'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac']}
        
        # Bỏ qua quảng cáo trong video Youtube (SponsorBlock)
        if 'youtube' in task_db.url:
            opts['sponsorblock_remove'] = ['sponsor', 'intro', 'outro', 'selfpromo']

    # [THỰC THI DOWNLOAD]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            print(f"🔗 Processing URL: {task_db.url}")
            
            info = ydl.extract_info(task_db.url, download=True)
            
            if not info:
                 raise Exception("Khong lay duoc thong tin video (Info is None)")

            # Xác định tên file cuối cùng
            if 'requested_downloads' in info:
                final_file = info['requested_downloads'][0]['filepath']
            else:
                final_file = ydl.prepare_filename(info)
                # Fix lỗi đuôi file sau khi convert (đôi khi yt-dlp trả về .webm nhưng đã convert sang .mp3)
                base, _ = os.path.splitext(final_file)
                if task_db.task_type == 'audio': 
                    final_file = f"{base}.{task_db.audio_format}"
                elif task_db.container == 'mp4' and not final_file.endswith('.mp4'):
                    final_file = f"{base}.mp4"

            # [QUAN TRỌNG] Chỉ lưu tên file (filename) vào DB, không lưu đường dẫn tuyệt đối
            # Để urls.py có thể ghép với MEDIA_URL
            task_db.filename = os.path.basename(final_file)
            
            task_db.status = 'FINISHED'
            task_db.progress = 100.0
            task_db.save()
            print(f"✅ DONE: {task_db.filename}")

    except Exception as e:
        task_db.status = 'FAILED'
        task_db.save()
        print(f"❌ ERROR DOWNLOAD: {str(e)}")


# --- TASK DỌN DẸP FILE RÁC (Chạy định kỳ bởi Celery Beat) ---
@shared_task
def clean_expired_files():
    """
    Dọn dẹp các file cũ hơn 1 tiếng đồng hồ để giải phóng ổ cứng server.
    """
    print("🧹 STARTING CLEANUP TASK...")
    now = time.time()
    expiration_time = 3600  # 3600 giây = 1 tiếng
    
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                
                if file_age > expiration_time:
                    try:
                        os.remove(filepath)
                        print(f"✅ Deleted old file: {filename}")
                    except Exception as e:
                        print(f"❌ Cannot delete {filename}: {e}")
    
    return "Cleanup Completed"