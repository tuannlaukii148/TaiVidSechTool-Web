#!/bin/bash

# 1. Chạy migrate database (Tự tạo bảng nếu chưa có)
echo "Dang chay Migrate Database..."
python manage.py migrate

# 2. Khởi động Supervisor (Quản lý Django + Celery)
echo "Dang khoi dong Server..."
/usr/bin/supervisord