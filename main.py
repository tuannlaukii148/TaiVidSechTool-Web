import os
import sys
import time
import yt_dlp
import pyperclip
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich import print as rprint

# --- CẤU HÌNH HỆ THỐNG ---
# Tự động lấy đường dẫn gốc của dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DIRS = {
    'cookies': os.path.join(BASE_DIR, 'cookies.txt'),
    'ffmpeg': os.path.join(BASE_DIR, 'bin', 'ffmpeg.exe'),
    'aria2c': os.path.join(BASE_DIR, 'bin', 'aria2c.exe'),
    'downloads': os.path.join(BASE_DIR, 'downloads'),
}

console = Console()

class HUSTDownloader:
    def __init__(self):
        self._check_system()

    def _check_system(self):
        """Kiểm tra sự tồn tại của các công cụ cốt lõi"""
        if not os.path.exists(DIRS['downloads']):
            os.makedirs(DIRS['downloads'])
        
        missing = []
        if not os.path.exists(DIRS['ffmpeg']): missing.append("FFmpeg (ffmpeg.exe)")
        if not os.path.exists(DIRS['aria2c']): missing.append("Aria2c (aria2c.exe)")
        
        if missing:
            console.print(Panel(f"[bold red]❌ THIẾU CÔNG CỤ TRONG THƯ MỤC 'bin':[/bold red]\n" + "\n".join(missing), title="Lỗi Hệ Thống"))
            console.print("[yellow]Vui lòng tải file .exe và bỏ vào folder 'bin' cùng cấp với main.py[/yellow]")
            sys.exit(1)
        
        self.use_cookies = os.path.exists(DIRS['cookies'])
        self._print_banner()

    def _print_banner(self):
        console.clear()
        banner = """
[bold cyan]🚀 HUST DOWNLOADER V7.1 - FINAL EDITION[/bold cyan]
[green]✔ Aria2c Speed[/green] | [yellow]✔ Windows Audio Fix[/yellow] | [magenta]✔ Force Overwrite[/magenta]
        """
        console.print(Panel(banner.strip(), border_style="cyan"))

    def get_opts(self, url, settings):
        """
        [CORE ENGINE] Cấu hình yt-dlp theo tiêu chuẩn V7.1
        """
        path_template = os.path.join(DIRS['downloads'], '%(extractor)s', '%(title).200s [%(id)s].%(ext)s')
        
        # Kiểm tra xem người dùng có muốn tải thêm (Extras) không
        want_sub = 'subtitle' in settings.get('extras', [])
        want_thumb = 'thumbnail' in settings.get('extras', [])

        opts = {
            # --- CẤU HÌNH CƠ BẢN ---
            'outtmpl': path_template,
            'ffmpeg_location': os.path.dirname(DIRS['ffmpeg']),
            'cookiefile': DIRS['cookies'] if self.use_cookies else None,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            
            # --- [V7.1] FORCE OVERWRITE (GHI ĐÈ KHÔNG HỎI) ---
            'overwrites': True,        # Cho phép ghi đè
            'force_overwrite': True,   # Bắt buộc ghi đè
            'no_continue': True,       # Không resume, tải mới từ 0% để tránh lỗi file
            
            # --- [V7.1] CLEAN & EMBED LOGIC ---
            'writethumbnail': want_thumb,
            'writesubtitles': want_sub,
            'embedthumbnail': want_thumb,   # Nhúng ảnh vào file
            'embedsubtitles': want_sub,     # Nhúng sub vào file
            'subtitleslangs': ['vi', 'en', 'en-US', 'all'] if want_sub else None,

            # --- [ACCELERATOR] ARIA2C ---
            'external_downloader': {'default': DIRS['aria2c']},
            'external_downloader_args': {'aria2c': ['-x', '16', '-k', '1M', '-s', '16']},
            
            # --- MẠNG & THỬ LẠI ---
            'retries': 10,
            'fragment_retries': 10,
        }

        # --- XỬ LÝ VIDEO ---
        if settings['type'] == 'video':
            res_limit = settings['resolution']
            container = settings['container'] 
            
            # Format String: Ưu tiên độ phân giải -> Fallback xuống thấp hơn nếu không có
            format_string = f"bestvideo[height<={res_limit}][ext={container}]+bestaudio/best[height<={res_limit}][ext={container}]/best"
            
            opts.update({
                'format': format_string,
                'merge_output_format': container,
                'subtitlesformat': 'srt' if container == 'mp4' else 'ass/srt/best',
            })

            # --- [WINDOWS FIX] ---
            # Ép convert âm thanh Opus sang AAC nếu container là MP4
            if container == 'mp4':
                opts['postprocessor_args'] = {'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac']}

            # --- [SPONSORBLOCK] (Youtube Only) ---
            if 'youtube' in url:
                opts['sponsorblock_remove'] = ['sponsor', 'intro', 'outro', 'selfpromo']

        # --- XỬ LÝ AUDIO ---
        elif settings['type'] == 'audio':
            audio_ext = settings['audio_format']
            bitrate = '320' if settings['audio_quality'] == 'best' else '128'
            
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': audio_ext, 'preferredquality': bitrate},
                    {'key': 'EmbedThumbnail'},
                    {'key': 'FFmpegMetadata'},
                ],
            })

        return opts

    def download(self, url, settings):
        opts = self.get_opts(url, settings)
        
        # Giao diện Loading 7 màu
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task("Khoi tao...", total=None)
            
            # Hook để cập nhật thanh tiến trình
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        # Lấy % từ output của yt-dlp/aria2c
                        p = d.get('_percent_str', '0%').replace('%', '')
                        progress.update(task_id, completed=float(p), description=f"[green]Downloading: {d.get('filename', 'File')}")
                    except: pass
                elif d['status'] == 'finished':
                    progress.update(task_id, description="[bold magenta]Processing (Embed/Convert/Clean)...")

            opts['progress_hooks'] = [progress_hook]

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', 'Unknown')
                    console.print(f"\n[bold yellow]➤ TARGET:[/bold yellow] {title}")
                    
                    # In thông số cấu hình
                    if settings['type'] == 'video':
                        extras = " + ".join([x.capitalize() for x in settings.get('extras', [])]) or "Clean Mode"
                        console.print(f"[i]Video: {settings['resolution']}p | {settings['container']} | [cyan]{extras}[/cyan][/i]")
                    else:
                        console.print(f"[i]Audio: {settings['audio_format']} | {settings['audio_quality']} mode[/i]")

                    ydl.download([url])
                    console.print(f"[bold green]✔ HOÀN TẤT! (Đã ghi đè & Dọn dẹp)[/bold green]")
            except Exception as e:
                console.print(f"[bold red]❌ LỖI:[/bold red] {str(e)}")

# --- CÁC HÀM TIỆN ÍCH (MODULES) ---

def get_user_settings_wizard():
    """Module Wizard: Menu trắc nghiệm"""
    mode = questionary.select("Bạn muốn tải gì?", choices=["Video", "Audio Only"]).ask()

    if "Video" in mode:
        res = questionary.select("Độ phân giải tối đa:", 
            choices=["2160 (4K)", "1440 (2K)", "1080 (Full HD)", "720 (HD)", "480 (SD)"]).ask()
        container = questionary.select("Đuôi file:", 
            choices=["mp4 (Tương thích Windows)", "mkv (Sub rời tốt)", "webm"]).ask().split()[0]
        
        # Checkbox chọn thành phần phụ
        extras = questionary.checkbox(
            "Tùy chọn tải thêm (Space để chọn):",
            choices=["Thumbnail (Ảnh bìa)", "Subtitle (Phụ đề)"]
        ).ask()
        
        mapped_extras = []
        if "Thumbnail" in str(extras): mapped_extras.append('thumbnail')
        if "Subtitle" in str(extras): mapped_extras.append('subtitle')

        return {'type': 'video', 'resolution': res.split()[0], 'container': container, 'extras': mapped_extras}
    else:
        fmt = questionary.select("Định dạng nhạc:", choices=["mp3", "m4a", "wav", "flac"]).ask().split()[0]
        qual = questionary.select("Chất lượng:", choices=["best (320kbps)", "medium (128kbps)"]).ask().split()[0]
        return {'type': 'audio', 'audio_format': fmt, 'audio_quality': qual, 'extras': ['thumbnail']}

def clipboard_monitor(downloader):
    """Module Automation: Theo dõi Clipboard"""
    console.print(Panel("[blink bold red]AUTO-CLIPBOARD: ON[/blink bold red]\nCopy link là tự tải. Mặc định: [cyan]1080p MP4 Clean[/cyan]", border_style="red"))
    last_text = ""
    try:
        while True:
            text = pyperclip.paste().strip()
            if text != last_text and text.startswith("http"):
                last_text = text
                
                # Logic thông minh phân loại nguồn
                if any(x in text for x in ['soundcloud', 'music.youtube', 'spotify']):
                     settings = {'type': 'audio', 'audio_format': 'mp3', 'audio_quality': 'best', 'extras': ['thumbnail']}
                else:
                     # Mặc định video là 1080p MP4 và KHÔNG tải sub/thumb để sạch máy
                     settings = {'type': 'video', 'resolution': '1080', 'container': 'mp4', 'extras': []}
                
                console.print(f"\n[DETECT] Link mới: {text}")
                downloader.download(text, settings)
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[STOP] Đã dừng chế độ tự động.")

def main():
    downloader = HUSTDownloader()
    while True:
        action = questionary.select(
            "MENU CHÍNH:",
            choices=[
                "🚀 Tải Link Mới (Wizard Mode)", 
                "⚡ Auto-Clipboard (Silent Mode)", 
                "❌ Thoát"
            ]
        ).ask()

        if "Thoát" in action: break
        elif "Auto-Clipboard" in action: clipboard_monitor(downloader)
        elif "Tải Link Mới" in action:
            url = questionary.text("Dán Link:").ask()
            if url:
                settings = get_user_settings_wizard()
                downloader.download(url, settings)
                questionary.text("Bấm Enter để tiếp tục...").ask()

if __name__ == "__main__":
    main()