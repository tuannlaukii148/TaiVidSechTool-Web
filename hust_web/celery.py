import os
from celery import Celery

# Thiết lập môi trường mặc định là settings của Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hust_web.settings')

app = Celery('hust_web')

# Load config từ settings.py (bắt đầu bằng CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tự động tìm task trong các app
app.autodiscover_tasks()