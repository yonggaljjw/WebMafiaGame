"""로비의 익명 세션 준비, 방 목록 조회, 방 생성을 담당하는 View입니다."""
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from game import engine
from game.models import Guest
from game.services import room_service

from .common import api, body, guest_id, reply, text_field


@require_GET
@ensure_csrf_cookie
@api
def bootstrap(request):
    """브라우저별 익명 Guest를 준비하고 방 생성 설정표를 전달합니다."""
    uid = request.session.get('guest_id')
    guest = Guest.objects.filter(pk=uid).first() if uid else None
    if not guest:
        guest = Guest.objects.create()
        request.session['guest_id'] = str(guest.pk)
    return reply({'room': guest.room_id, 'settings_catalog': engine.settings_catalog()})


@require_GET
@api
def rooms(request):
    """현재 입장 가능한 대기방만 반환합니다."""
    return reply({'rooms': room_service.list_waiting_rooms()})


@require_POST
@api
def create_room(request):
    """방 생성 입력을 검증한 뒤 서비스 계층에 실제 생성을 맡깁니다."""
    data = body(request)
    nickname = text_field(data, 'nickname', 1, 12)
    title = text_field(data, 'title', 1, 40)
    capacity = data.get('capacity', 8)

    # 이전 클라이언트의 day_seconds 필드도 유지하면서 새 역할/시간 설정을 함께 검증합니다.
    config = engine.validate_settings(
        capacity,
        data.get('role_counts'),
        {
            'day': data.get('day_seconds', 90),
            'vote': data.get('vote_seconds', 30),
            'night': data.get('night_seconds', 30),
        },
    )
    result = room_service.create_room_for_guest(
        guest_id(request), nickname, title, capacity, config
    )
    return reply(result, 201)
