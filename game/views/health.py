"""컨테이너/프록시가 사용할 상태 확인 엔드포인트입니다."""
import logging

from django.db import connection
from django.views.decorators.http import require_GET

from .common import reply

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    """Django뿐 아니라 실제 DB 연결까지 확인합니다."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return reply({'status': 'ok'})
    except Exception:
        logger.exception('Database health check failed')
        return reply({'status': 'unavailable'}, 503)
