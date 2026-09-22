"""HTML 페이지를 렌더링하는 View입니다."""
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET


@require_GET
@ensure_csrf_cookie
def index(request):
    """SPA 형태의 단일 게임 화면을 렌더링하고 CSRF 쿠키를 준비합니다."""
    return render(request, 'game/index.html')
