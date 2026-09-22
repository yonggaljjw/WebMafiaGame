"""여러 API View에서 공통으로 사용하는 HTTP 입출력 도우미입니다."""
import json
from functools import wraps

from django.http import JsonResponse

from game import engine
from game.models import Guest, Room


def reply(data, status=200):
    """한국어 JSON을 그대로 보여주고 캐시하지 않는 공통 응답입니다."""
    response = JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})
    response['Cache-Control'] = 'no-store'
    return response


def api(fn):
    """API에서 공통으로 처리할 예외를 JSON 오류 응답으로 바꿉니다."""
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
    """JSON 요청 본문을 dict로 읽습니다."""
    data = json.loads(request.body or '{}')
    engine.require(isinstance(data, dict), '객체 형식의 요청이 필요합니다.')
    return data


def guest_id(request):
    """Django 세션에 저장된 익명 Guest ID를 가져옵니다."""
    uid = request.session.get('guest_id')
    engine.require(bool(uid), '먼저 로비를 새로고침하세요.')
    return uid


def text_field(data, key, minimum, maximum):
    """닉네임/방 제목 같은 짧은 문자열을 공통 규칙으로 검사합니다."""
    value = data.get(key, '')
    engine.require(isinstance(value, str), '문자열 입력이 필요합니다.')
    value = value.strip()
    engine.require(
        minimum <= len(value) <= maximum and not any(ord(c) < 32 for c in value),
        f'{key}: {minimum}~{maximum}자로 입력하세요.',
    )
    return value


def csrf_failure(request, reason=''):
    """Django의 CSRF 검증 실패도 다른 API 오류와 같은 JSON 형태로 반환합니다."""
    return reply({
        'error': '허용되지 않은 요청입니다. 새로고침 후에도 같다면 .env의 허용 호스트·CSRF 출처를 확인하세요.'
    }, 403)
