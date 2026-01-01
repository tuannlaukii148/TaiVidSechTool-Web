#!/bin/bash

# --- BƯỚC 1: TẠO COOKIE (Vượt qua chặn Youtube) ---
# Kiểm tra xem có biến COOKIES_CONTENT không, nếu có thì ghi ra file
if [ ! -z "$COOKIES_CONTENT" ]; then
    echo "$COOKIES_CONTENT" > cookies.txt
    echo "✅ Da tao file cookies.txt tu bien moi truong."
else
    echo "⚠️ Canh bao: Khong tim thay bien COOKIES_CONTENT. Youtube co the bi chan."
fi

# --- BƯỚC 2: GOM FILE TĨNH (QUAN TRỌNG ĐỂ HIỆN LOGO) ---
# Lệnh này sẽ copy ảnh từ thư mục 'static' vào 'staticfiles'
echo "📦 Dang gom file static (Collectstatic)..."
python manage.py collectstatic --noinput

# --- BƯỚC 3: DATABASE ---
echo "🔄 Dang chay Migrate Database..."
python manage.py migrate

# --- BƯỚC 4: KHỞI ĐỘNG SERVER ---
echo "🚀 Dang khoi dong Supervisor..."
/usr/bin/supervisord