# views.py
from django.shortcuts import render, redirect
from .models import UserInfo, Story, StoryImage
from .story_generator import generate_story_with_images
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .chatbot import ask_chatbot
from threading import Thread
import json

@csrf_exempt
def chatbot_view(request):
    if request.method == 'POST':
        user_input = request.POST.get('user_input')
        response = ask_chatbot(user_input)
        return JsonResponse({'response': response})

def landing(request):
    return render(request, 'myapp/landing.html')

def storyinfo(request):
    if request.method == 'POST':
        user_info = UserInfo.objects.create(
            name=request.POST['name'],
            age=request.POST['age'],
            country_of_interest=request.POST['country'],
            interests=request.POST['interests'],
        )
        return redirect('loading')
    return render(request, 'myapp/storyinfo.html')

def loading(request):
    user_info = UserInfo.objects.last()
    
    story = Story.objects.create(
        user_info=user_info,
        title=f"{user_info.name}의 {user_info.country_of_interest} 여행",
        content="",
        voice_type=user_info.voice_type
    )
    
    generate_story_async(story.id, user_info)
    
    return render(request, 'myapp/loading.html', {'story_id': story.id})

def check_story_status(request, story_id):
    story = Story.objects.get(id=story_id)
    status = 'completed' if story.content else 'in_progress'
    return JsonResponse({'status': status})

def story(request, story_id):
    story = Story.objects.get(id=story_id)
    images = story.images.order_by('page_number')
    pages = story.content.split('\n\n')
    content = [{'text': pages[i], 'image_url': images[i].image_url if i < len(images) else ''} 
               for i in range(len(pages))]
    content_json = json.dumps(content)
    return render(request, 'myapp/story.html', {'story': story, 'content': content_json})

def end(request):
    return render(request, 'myapp/end.html')

def generate_story_async(story_id, user_info):
    def task():
        story_content, images = generate_story_with_images(
            name=user_info.name,
            age=user_info.age,
            country=user_info.country_of_interest,
            interests=user_info.interests
        )
        story = Story.objects.get(id=story_id)
        story.content = story_content
        story.save()
        
        for i, image_url in enumerate(images):
            if image_url:  # image_url이 None이 아닌 경우에만 StoryImage 생성
                StoryImage.objects.create(story=story, image_url=image_url, page_number=i)
    
    Thread(target=task).start()

# Google cloud tts
from django.http import HttpResponse
import json
import requests
import time

# Typecast API 설정
API_URL = "https://typecast.ai/api/speak"
API_TOKEN = f'Bearer {os.getenv("TYPECAST_API_KEY")}'
HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': API_TOKEN
}

def generate_tts_audio(text):
    """Typecast API로 음성 생성 요청."""
    payload = {
        "actor_id": "6080369d3211aa112ab131db",
        "text": text,
        "lang": "auto",
        "tempo": 1,
        "volume": 100,
        "pitch": 0,
        "xapi_hd": True,
        "max_seconds": 60,
        "model_version": "latest",
        "xapi_audio_format": "wav"
    }

    response = requests.post(API_URL, headers=HEADERS, data=json.dumps(payload))
    if response.status_code == 200:
        return response.json()["result"]["speak_v2_url"]
    else:
        raise Exception(f"TTS 생성 실패: {response.status_code}, {response.text}")

def poll_audio_url(speak_url):
    """폴링으로 음성 파일 준비 여부 확인."""
    while True:
        response = requests.get(speak_url, headers=HEADERS)
        result = response.json()["result"]
        if result["status"] == "done":
            return result["audio_download_url"]
        time.sleep(1)

@csrf_exempt
def tts_view(request):
    """Typecast API를 사용한 TTS 요청 처리."""
    if request.method == 'POST':
        data = json.loads(request.body)
        text = data.get('text', '')

        try:
            speak_url = generate_tts_audio(text)
            audio_url = poll_audio_url(speak_url)

            audio_response = requests.get(audio_url, headers=HEADERS)
            return HttpResponse(audio_response.content, content_type='audio/wav')

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return HttpResponse(status=405)



from .models import UserInfo, Story, StoryImage, LanguageExpression

def languagestudy(request):
    user_info = UserInfo.objects.last()
    country = user_info.country_of_interest
    expressions = LanguageExpression.objects.filter(country=country)
    
    # 각 표현에 대해 오디오 파일 URL 추가
    for expression in expressions:
        if expression.audio_file:
            expression.audio_url = expression.audio_file.url
        else:
            expression.audio_url = None
    
    return render(request, 'myapp/languagestudy.html', {'country': country, 'expressions': expressions})
