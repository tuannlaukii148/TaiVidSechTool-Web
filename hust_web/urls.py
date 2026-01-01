from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('api/start/', views.start_download_api),
    path('api/status/<uuid:task_id>/', views.check_status_api),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)