"""URL 설정이 간단하도록 기능별 View를 한 곳에서 다시 공개합니다.

``config/urls.py``는 기존처럼 ``from game import views``를 유지할 수 있고,
실제 코드는 lobby.py / room.py / pages.py / health.py로 나뉘어 있습니다.
"""
from .common import csrf_failure, reply
from .health import health
from .lobby import bootstrap, create_room, rooms
from .pages import index
from .room import join_room, room_action, sync_room

# 이전 코드에서 game.views.tick_room/save_room을 가져오던 경우도 깨지지 않게 호환성을 유지합니다.
from game.services.room_service import save_room, tick_room

__all__ = [
    'index', 'bootstrap', 'rooms', 'create_room', 'join_room',
    'sync_room', 'room_action', 'health', 'csrf_failure', 'reply',
    'tick_room', 'save_room',
]
