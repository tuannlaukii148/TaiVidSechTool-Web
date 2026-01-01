from django.db import models
import uuid

class DownloadTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField()
    status = models.CharField(max_length=20, default='PENDING') # PENDING, DOWNLOADING, PROCESSING, FINISHED, FAILED
    progress = models.FloatField(default=0.0)
    filename = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # --- CÁC TÙY CHỌN TỪ BẢN CLI V7.1 ---
    # Loại tải: 'video' hoặc 'audio'
    task_type = models.CharField(max_length=10, default='video') 
    
    # Video Options
    resolution = models.CharField(max_length=10, default='1080') # 2160, 1440, 1080...
    container = models.CharField(max_length=10, default='mp4')   # mp4, mkv, webm
    
    # Audio Options
    audio_format = models.CharField(max_length=10, default='mp3') # mp3, m4a, flac...
    audio_quality = models.CharField(max_length=10, default='best') # best (320), medium (128)
    
    # Extras (Clean Mode Options)
    use_subtitle = models.BooleanField(default=False)
    use_thumbnail = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.url} - {self.status}"