"""HTTP 계층: 입력 검증 → 익명 세션 확인 → DB 잠금 → 규칙 엔진 → 공개 상태 응답."""
import json
import logging
import secrets
import time
from functools import wraps
from django.conf import settings
from django.db import transaction, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from .models import Guest, Room
from . import engine

logger = logging.getLogger(__name__)

def reply(data, status=200):
    response = JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})
    response['Cache-Control'] = 'no-store'
    return response

def api(fn):
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        try:
            return fn(request, *args, **kwargs)
        except engine.RuleError as exc:
            return reply({'error': str(exc)}, 400)
        except (Room.DoesNotExist, Guest.DoesNotExist):
            return reply({'error': '방 또는 세션이 없습니다. 로비를 새로고침하세요.'}, 404)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return reply({'error': 'JSON 형식이 올바르지 않습니다.'}, 400)
    return wrapped

def body(request):
    data = json.loads(request.body or '{}')
    engine.require(isinstance(data, dict), '객체 형식의 요청이 필요합니다.')
    return data

def guest_id(request):
    uid = request.session.get('guest_id')
    engine.require(bool(uid), '먼저 로비를 새로고침하세요.')
    return uid

def text_field(data, key, minimum, maximum):
    value = data.get(key, '')
    engine.require(isinstance(value, str), '문자열 입력이 필요합니다.')
    value = value.strip()
    engine.require(minimum <= len(value) <= maximum and not any(ord(c) < 32 for c in value),
                   f'{key}: {minimum}~{maximum}자로 입력하세요.')
    return value

def tick_room(room, now):
    engine.tick(room.state, now, settings.PRESENCE_STALE_SECONDS,
                settings.DISCONNECT_GRACE_SECONDS, settings.CLOCK_FAILURE_SECONDS)

def save_room(room):
    room.status = room.state['phase']
    room.save(update_fields=['state', 'status', 'updated_at'])

def room_response(room, uid, now):
    return {'code': room.code, 'title': room.title, 'capacity': room.capacity,
            **engine.snapshot(room.state, uid, now, settings.PRESENCE_STALE_SECONDS, settings.DISCONNECT_GRACE_SECONDS)}

def clear_old_room(guest):
    # Guest → Room 순서로 잠급니다. 모든 입장/행동이 같은 잠금 순서를 지킵니다.
    if guest.room_id:
        old = Room.objects.select_for_update().get(pk=guest.room_id)
        tick_room(old, time.time())
        save_room(old)
        member = old.state['players'].get(str(guest.pk))
        engine.require(not member or member['left'] or old.status == 'closed', '이미 참여 중인 방에서 먼저 나가세요.')
        guest.room = None

def csrf_failure(request, reason=''):
    return reply({'error': '허용되지 않은 요청입니다. 새로고침 후에도 같다면 .env의 허용 호스트·CSRF 출처를 확인하세요.'}, 403)

@require_GET
@ensure_csrf_cookie
def index(request):
    return render(request, 'game/index.html')

@require_GET
@ensure_csrf_cookie
@api
def bootstrap(request):
    uid = request.session.get('guest_id')
    guest = Guest.objects.filter(pk=uid).first() if uid else None
    if not guest:
        guest = Guest.objects.create()
        request.session['guest_id'] = str(guest.pk)
    return reply({'room': guest.room_id, 'settings_catalog': engine.settings_catalog()})

@require_GET
@api
def rooms(request):
    now = time.time()
    result = []
    for room in Room.objects.filter(status='waiting').order_by('-created_at')[:100]:
        count = sum(now - p['last_seen'] < settings.DISCONNECT_GRACE_SECONDS for p in engine.players(room.state).values())
        if count:
            result.append({'code': room.code, 'title': room.title, 'capacity': room.capacity, 'count': count})
    return reply({'rooms': result})

@require_POST
@api
def create_room(request):
    data = body(request)
    nickname = text_field(data, 'nickname', 1, 12)
    title = text_field(data, 'title', 1, 40)
    capacity = data.get('capacity', 8)
    # 기존 day_seconds 필드도 지원하면서 세 단계 설정을 함께 검증합니다.
    config = engine.validate_settings(capacity, data.get('role_counts'), {
        'day': data.get('day_seconds', 90), 'vote': data.get('vote_seconds', 30),
        'night': data.get('night_seconds', 30),
    })
    now = time.time()
    with transaction.atomic():
        guest = Guest.objects.select_for_update().get(pk=guest_id(request))
        clear_old_room(guest)
        engine.require(now - guest.last_create >= 10, '방 생성 후 10초 뒤에 다시 시도하세요.')
        code = secrets.token_hex(4).upper()
        room = Room.objects.create(code=code, title=title, capacity=capacity,
               state=engine.new_state(str(guest.pk), nickname, now, game_settings=config))
        guest.room, guest.last_create = room, now
        guest.save(update_fields=['room', 'last_create'])
        return reply(room_response(room, str(guest.pk), now), 201)

@require_POST
@api
def join_room(request, code):
    nickname = text_field(body(request), 'nickname', 1, 12)
    with transaction.atomic():
        guest = Guest.objects.select_for_update().get(pk=guest_id(request))
        uid = str(guest.pk)
        if guest.room_id == code:
            room = Room.objects.select_for_update().get(pk=code)
            now = time.time()
            tick_room(room, now)
            p = room.state['players'].get(uid)
            if p and not p['left']:
                p['last_seen'] = now
                save_room(room)
                return reply(room_response(room, uid, now))
            save_room(room)
        clear_old_room(guest)
        room = Room.objects.select_for_update().get(pk=code)
        now = time.time()
        tick_room(room, now)
        # 상태를 확인하고 인원을 추가하는 전체 작업이 하나의 행 잠금 안에서 실행됩니다.
        engine.require(len(engine.players(room.state)) < room.capacity, '방이 가득 찼습니다.')
        engine.join(room.state, uid, nickname, now)
        save_room(room)
        guest.room = room
        guest.save(update_fields=['room'])
        return reply(room_response(room, uid, now))

def with_room(request, code, do_action=False):
    payload = body(request)
    if do_action:
        engine.require(isinstance(payload.get('kind'), str), '행동 종류가 올바르지 않습니다.')
    with transaction.atomic():
        guest = Guest.objects.select_for_update().get(pk=guest_id(request))
        uid = str(guest.pk)
        engine.require(guest.room_id == code, '참여 중인 방이 아닙니다.')
        room = Room.objects.select_for_update().get(pk=code)
        now = time.time()
        # 유예가 이미 끝난 세션을 heartbeat로 부활시키지 않도록 먼저 이탈을 판정합니다.
        tick_room(room, now)
        p = room.state['players'].get(uid)
        if not p or p['left'] or room.status == 'closed':
            guest.room = None
            guest.save(update_fields=['room'])
            save_room(room)
            return reply({'error': '재접속 유예가 끝나 방에서 퇴장했습니다.', 'left': True}, 410)
        p['last_seen'] = now
        # 마지막 재접속자의 heartbeat를 반영해 일시정지를 즉시 해제합니다.
        tick_room(room, now)
        error = None
        if do_action:
            try:
                engine.action(room.state, uid, payload.get('kind'), payload, now)
            except engine.RuleError as exc:
                error = str(exc)
        save_room(room)
        if p['left']:
            guest.room = None
            guest.save(update_fields=['room'])
            return reply({'left': True})
        response = room_response(room, uid, now)
        if error:
            response['error'] = error
        return reply(response, 400 if error else 200)

@require_POST
@api
def sync_room(request, code):
    return with_room(request, code)

@require_POST
@api
def room_action(request, code):
    return with_room(request, code, True)

@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return reply({'status': 'ok'})
    except Exception:
        logger.exception('Database health check failed')
        return reply({'status': 'unavailable'}, 503)
