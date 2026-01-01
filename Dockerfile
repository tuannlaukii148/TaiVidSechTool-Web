# Dùng Python 3.10 trên nền Linux nhẹ
FROM python:3.10-slim

# 1. Cài đặt FFmpeg, Aria2c và Redis-tools (Client)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    aria2 \
    git \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 2. Thiết lập thư mục làm việc
WORKDIR /app

# 3. Copy file thư viện và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy toàn bộ code vào
COPY . .

# 5. Tạo thư mục chứa file tải về
RUN mkdir -p media/downloads

# 6. Copy file cấu hình Supervisor (sẽ tạo ở bước 3)
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 7. Mở Port 8000
EXPOSE 8000

# 8. Lệnh chạy mặc định
CMD ["/usr/bin/supervisord"]