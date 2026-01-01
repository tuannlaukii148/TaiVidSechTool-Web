import os
from pathlib import Path
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Đọc cấu hình bảo mật từ .env
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-hust-secret-key-default')

# Chuyển đổi chuỗi 'True'/'False' từ .env thành Boolean
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# Tách chuỗi bằng dấu phẩy
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# [QUAN TRỌNG] Fix lỗi CSRF trên Render (Để bấm nút tải không bị chặn)
CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',                  # App của mình
    'django_celery_results', # Lưu kết quả
    'django_celery_beat',    # [MỚI] Thêm cái này để lưu lịch vào DB
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware', # (Dành cho nâng cao sau này)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hust_web.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hust_web.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --- CẤU HÌNH STATIC FILES (CSS, JS, IMAGES) ---
STATIC_URL = '/static/'

# 1. Nơi để file ảnh gốc khi code (Folder 'static' ở máy bạn)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# 2. [THÊM MỚI] Nơi Django gom file về khi chạy trên Server (Bắt buộc)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# --- CẤU HÌNH MEDIA (Nơi chứa file tải về) ---
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# --- CẤU HÌNH CELERY ---
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_TIMEZONE = 'Asia/Ho_Chi_Minh'

# --- CELERY BEAT SCHEDULE ---
from celery.schedules import crontab

# [FIX LỖI DBM ERROR] Lưu lịch trình vào Database thay vì File
CELERY_BEAT_SCHEDULER = 'django_celery_results.schedulers.DatabaseScheduler'

CELERY_BEAT_SCHEDULE = {
    'clean-every-hour': {
        'task': 'core.tasks.clean_expired_files',
        'schedule': 3600.0,
    },
}