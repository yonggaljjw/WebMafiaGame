"""브라우저가 모두 닫혀도 이탈·시간 만료를 처리하는 별도 프로세스입니다."""
import logging
import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from game.models import Room
from game.services.room_service import tick_room, save_room

class Command(BaseCommand):
    help = '1초마다 진행 중인 방을 점검합니다. Ctrl+C로 종료합니다.'

    def handle(self, *args, **options):
        logger = logging.getLogger(__name__)
        self.stdout.write('게임 시계 시작')
        try:
            while True:
                started = time.monotonic()
                close_old_connections()
                try:
                    codes = list(Room.objects.exclude(status='closed').values_list('pk', flat=True))
                    for code in codes:
                        try:
                            with transaction.atomic():
                                room = Room.objects.select_for_update().get(pk=code)
                                tick_room(room, time.time())
                                save_room(room)
                        except Room.DoesNotExist:
                            pass
                except Exception:
                    # DB 복구 후 다시 검사합니다. 오래 지연된 게임은 엔진이 무효 종료합니다.
                    logger.exception('게임 시계 점검 실패')
                time.sleep(max(0.05, 1 - (time.monotonic() - started)))
        except KeyboardInterrupt:
            self.stdout.write('게임 시계 종료')
