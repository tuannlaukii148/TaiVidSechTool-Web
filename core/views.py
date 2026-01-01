from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import DownloadTask
from .tasks import process_download_task
import json

def index(request):
    return render(request, 'index.html')

@csrf_exempt
def start_download_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        
        # Tạo Task với đầy đủ tùy chọn
        task = DownloadTask.objects.create(
            url=data.get('url'),
            task_type=data.get('task_type', 'video'),
            resolution=data.get('resolution', '1080'),
            container=data.get('container', 'mp4'),
            audio_format=data.get('audio_format', 'mp3'),
            audio_quality=data.get('audio_quality', 'best'),
            use_subtitle=data.get('use_subtitle', False),
            use_thumbnail=data.get('use_thumbnail', False),
        )
        
        # Đẩy vào Celery
        process_download_task.delay(task.id)
        return JsonResponse({'task_id': task.id})

def check_status_api(request, task_id):
    try:
        task = DownloadTask.objects.get(id=task_id)
        return JsonResponse({
            'status': task.status,
            'progress': task.progress,
            # Trả về link download file
            'download_url': f"/media/downloads/{task.filename}" if task.status == 'FINISHED' else None
        })
    except:
        return JsonResponse({'error': 'Not found'}, status=404)