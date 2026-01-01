from django.contrib import admin
from django.urls import path, re_path
from django.conf import settings
from django.views.static import serve
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('api/start/', views.start_download_api),
    path('api/status/<uuid:task_id>/', views.check_status_api),

    # === [QUAN TRỌNG] FIX LỖI 404 MEDIA TRÊN RENDER ===
    # Ép Django phục vụ file Media (Video tải về) và Static (CSS/JS)
    # ngay cả khi chạy ở chế độ Production (DEBUG=False)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    # ==================================================
]