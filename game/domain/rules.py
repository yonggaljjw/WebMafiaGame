"""게임의 고정 규칙과 방 설정 검증을 담당합니다.

이 모듈은 Django의 Request/Response나 데이터베이스를 전혀 알지 못합니다.
따라서 역할 밸런스나 시간 제한처럼 '게임 규칙 그 자체'만 공부하고 싶을 때
가장 먼저 읽기 좋은 파일입니다.
"""

ACTIVE = {'day', 'vote', 'night'}
ROLE_NAMES = {'mafia': '마피아', 'doctor': '의사', 'police': '경찰', 'citizen': '시민'}
TIME_LIMITS = {'day': (30, 300), 'vote': (15, 120), 'night': (15, 120)}


class RuleError(Exception):
    """사용자의 행동이 현재 게임 규칙에 맞지 않을 때 발생시키는 예외입니다."""


def require(condition, message):
    """조건이 거짓이면 RuleError를 발생시키는 작은 검증 도우미입니다."""
    if not condition:
        raise RuleError(message)


def balance_limits(n):
    """시작 인원별 역할 최대 인원을 계산합니다."""
    require(type(n) is int and 4 <= n <= 12, '시작 인원은 4~12명입니다.')
    return {
        'mafia': (n - 1) // 3,
        'police': 1 if n < 10 else 2,
        'doctor': 1 if n < 8 else 2,
        'citizen': n - 1,
    }


def default_roles(n):
    """역할 수를 직접 지정하지 않았을 때 사용할 기본 구성을 만듭니다."""
    limits = balance_limits(n)
    return {
        'mafia': limits['mafia'],
        'police': 1,
        'doctor': 1,
        'citizen': n - limits['mafia'] - 2,
    }


def validate_settings(n, roles=None, durations=None):
    """UI를 우회한 요청도 서버에서 동일한 기준으로 다시 검사합니다."""
    limits = balance_limits(n)
    roles = default_roles(n) if roles is None else roles
    durations = {'day': 90, 'vote': 30, 'night': 30} if durations is None else durations

    require(isinstance(roles, dict) and set(roles) == set(ROLE_NAMES), '네 역할의 인원을 모두 지정하세요.')
    for role, value in roles.items():
        minimum = 1 if role in {'mafia', 'citizen'} else 0
        # bool은 int의 하위 타입이므로 type(value) is int로 엄격하게 검사합니다.
        require(
            type(value) is int and minimum <= value <= limits[role],
            f'{ROLE_NAMES[role]}은 {minimum}~{limits[role]}명으로 설정하세요.',
        )

    require(sum(roles.values()) == n, '역할 인원 합계는 시작 인원과 같아야 합니다.')
    require(
        roles['police'] + roles['doctor'] <= roles['mafia'] + 1,
        '경찰+의사는 마피아 수+1명 이하여야 합니다. 시민팀 특수직업 과밀을 제한합니다.',
    )

    require(
        isinstance(durations, dict) and set(durations) == set(TIME_LIMITS),
        '세 단계의 시간을 모두 지정하세요.',
    )
    for phase, value in durations.items():
        low, high = TIME_LIMITS[phase]
        require(type(value) is int and low <= value <= high, f'{phase} 시간은 {low}~{high}초의 정수여야 합니다.')

    # 입력 객체와 참조를 끊어, 호출자가 원본 dict를 수정해도 저장된 설정이 변하지 않게 합니다.
    return {'player_count': n, 'roles': dict(roles), 'durations': dict(durations)}


def settings_catalog():
    """프런트가 방 생성 UI를 그릴 때 사용할 공개 설정표입니다."""
    return {
        'by_players': {
            str(n): {'limits': balance_limits(n), 'defaults': default_roles(n)}
            for n in range(4, 13)
        },
        'time_limits': TIME_LIMITS,
        'special_extra': 1,
    }
