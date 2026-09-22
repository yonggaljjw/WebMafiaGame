"""Room/Guest 모델과 게임 엔진 사이를 연결하는 애플리케이션 서비스입니다.

Django View가 직접 ``select_for_update``와 상태 저장을 반복하지 않도록
DB 트랜잭션과 방 상태 변경 로직을 이 모듈에 모았습니다.

학습 포인트
-----------
1. View: HTTP 입력/출력에 집중
2. Service: ORM, 트랜잭션, 행 잠금에 집중
3. Domain(engine): 순수 게임 규칙에 집중
"""
import secrets
import time

from django.conf import settings
from django.db import transaction

from game import engine
from game.models import Guest, Room


def tick_room(room, now):
    """서버 시계를 한 번 진행합니다. 아직 DB 저장은 하지 않습니다."""
    engine.tick(
        room.state,
        now,
        settings.PRESENCE_STALE_SECONDS,
        settings.DISCONNECT_GRACE_SECONDS,
        settings.CLOCK_FAILURE_SECONDS,
    )


def save_room(room):
    """JSON 상태와 검색용 status를 함께 저장합니다."""
    room.status = room.state['phase']
    room.save(update_fields=['state', 'status', 'updated_at'])


def room_response(room, uid, now):
    """현재 참가자에게 공개 가능한 방 상태만 API 응답 형태로 만듭니다."""
    return {
        'code': room.code,
        'title': room.title,
        'capacity': room.capacity,
        **engine.snapshot(
            room.state,
            uid,
            now,
            settings.PRESENCE_STALE_SECONDS,
            settings.DISCONNECT_GRACE_SECONDS,
        ),
    }


def clear_old_room(guest):
    """새 방 입장 전 기존 방 연결이 정리되었는지 확인합니다.

    Guest → Room 순서로 잠그는 규칙을 모든 입장/행동에서 동일하게 지켜
    서로 반대 순서로 잠그다가 교착 상태가 생길 가능성을 줄입니다.
    """
    if not guest.room_id:
        return

    old = Room.objects.select_for_update().get(pk=guest.room_id)
    tick_room(old, time.time())
    save_room(old)
    member = old.state['players'].get(str(guest.pk))
    engine.require(
        not member or member['left'] or old.status == 'closed',
        '이미 참여 중인 방에서 먼저 나가세요.',
    )
    guest.room = None


def list_waiting_rooms(now=None):
    """로비에 보여줄 대기 중 방 목록을 만듭니다."""
    now = time.time() if now is None else now
    result = []
    for room in Room.objects.filter(status='waiting').order_by('-created_at')[:100]:
        count = sum(
            now - p['last_seen'] < settings.DISCONNECT_GRACE_SECONDS
            for p in engine.players(room.state).values()
        )
        if count:
            result.append({
                'code': room.code,
                'title': room.title,
                'capacity': room.capacity,
                'count': count,
            })
    return result


def create_room_for_guest(uid, nickname, title, capacity, config, now=None):
    """방 생성 전체 과정을 하나의 트랜잭션에서 처리합니다."""
    now = time.time() if now is None else now
    with transaction.atomic():
        guest = Guest.objects.select_for_update().get(pk=uid)
        clear_old_room(guest)
        engine.require(now - guest.last_create >= 10, '방 생성 후 10초 뒤에 다시 시도하세요.')

        code = secrets.token_hex(4).upper()
        room = Room.objects.create(
            code=code,
            title=title,
            capacity=capacity,
            state=engine.new_state(str(guest.pk), nickname, now, game_settings=config),
        )
        guest.room = room
        guest.last_create = now
        guest.save(update_fields=['room', 'last_create'])
        return room_response(room, str(guest.pk), now)


def join_room_for_guest(uid, code, nickname):
    """대기방 입장 또는 동일 세션의 재입장을 처리합니다."""
    with transaction.atomic():
        guest = Guest.objects.select_for_update().get(pk=uid)
        guest_uid = str(guest.pk)

        # 같은 방을 새로고침한 경우에는 새 참가자를 만들지 않고 heartbeat만 갱신합니다.
        if guest.room_id == code:
            room = Room.objects.select_for_update().get(pk=code)
            now = time.time()
            tick_room(room, now)
            player = room.state['players'].get(guest_uid)
            if player and not player['left']:
                player['last_seen'] = now
                save_room(room)
                return room_response(room, guest_uid, now)
            save_room(room)

        clear_old_room(guest)
        room = Room.objects.select_for_update().get(pk=code)
        now = time.time()
        tick_room(room, now)

        # 정원 확인과 실제 추가가 같은 행 잠금 안에서 수행되므로 동시 입장에도 정원을 넘지 않습니다.
        engine.require(len(engine.players(room.state)) < room.capacity, '방이 가득 찼습니다.')
        engine.join(room.state, guest_uid, nickname, now)
        save_room(room)

        guest.room = room
        guest.save(update_fields=['room'])
        return room_response(room, guest_uid, now)


def update_room_for_guest(uid, code, payload, do_action=False):
    """heartbeat(sync)와 실제 게임 행동(action)의 공통 잠금 흐름입니다."""
    if do_action:
        engine.require(isinstance(payload.get('kind'), str), '행동 종류가 올바르지 않습니다.')

    with transaction.atomic():
        guest = Guest.objects.select_for_update().get(pk=uid)
        guest_uid = str(guest.pk)
        engine.require(guest.room_id == code, '참여 중인 방이 아닙니다.')

        room = Room.objects.select_for_update().get(pk=code)
        now = time.time()

        # 유예가 이미 끝났다면 늦게 도착한 heartbeat로 참가자를 되살리지 않습니다.
        tick_room(room, now)
        player = room.state['players'].get(guest_uid)
        if not player or player['left'] or room.status == 'closed':
            guest.room = None
            guest.save(update_fields=['room'])
            save_room(room)
            return {'error': '재접속 유예가 끝나 방에서 퇴장했습니다.', 'left': True}, 410

        player['last_seen'] = now
        # 마지막 재접속자의 heartbeat가 들어오면 일시정지가 즉시 해제될 수 있게 다시 tick합니다.
        tick_room(room, now)

        error = None
        if do_action:
            try:
                engine.action(room.state, guest_uid, payload.get('kind'), payload, now)
            except engine.RuleError as exc:
                error = str(exc)

        save_room(room)

        if player['left']:
            guest.room = None
            guest.save(update_fields=['room'])
            return {'left': True}, 200

        response = room_response(room, guest_uid, now)
        if error:
            response['error'] = error
        return response, 400 if error else 200
