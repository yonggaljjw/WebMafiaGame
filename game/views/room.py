"""특정 방의 입장, 상태 동기화, 게임 행동 API를 담당하는 View입니다."""
from django.views.decorators.http import require_POST

from game.services import room_service

from .common import api, body, guest_id, reply, text_field


@require_POST
@api
def join_room(request, code):
    """닉네임을 검증하고 방 입장 서비스 호출 결과를 반환합니다."""
    nickname = text_field(body(request), 'nickname', 1, 12)
    return reply(room_service.join_room_for_guest(guest_id(request), code, nickname))


def _with_room(request, code, do_action=False):
    """sync/action View가 공유하는 얇은 HTTP 어댑터입니다."""
    payload = body(request)
    result, status = room_service.update_room_for_guest(
        guest_id(request), code, payload, do_action=do_action
    )
    return reply(result, status)


@require_POST
@api
def sync_room(request, code):
    """1초 폴링 heartbeat를 반영하고 최신 공개 상태를 반환합니다."""
    return _with_room(request, code)


@require_POST
@api
def room_action(request, code):
    """채팅·준비·투표·능력·퇴장 등 참가자 행동을 처리합니다."""
    return _with_room(request, code, do_action=True)
