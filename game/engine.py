"""기존 import 경로를 유지하는 게임 엔진 파사드(facade)입니다.

이전 코드와 테스트는 계속 ``from game import engine``을 사용할 수 있습니다.
실제 구현은 학습하기 쉽도록 ``game/domain`` 아래의 기능별 모듈로 분리했습니다.
"""
from .domain.actions import action
from .domain.phases import enter_phase, resolve_phase, start, tick, unique_target
from .domain.rules import (
    ACTIVE,
    ROLE_NAMES,
    TIME_LIMITS,
    RuleError,
    balance_limits,
    default_roles,
    require,
    settings_catalog,
    validate_settings,
)
from .domain.snapshot import snapshot
from .domain.state import (
    alive,
    check_win,
    finish,
    join,
    log,
    new_state,
    players,
    remove_players,
    transfer_host,
)

__all__ = [
    'ACTIVE', 'ROLE_NAMES', 'TIME_LIMITS', 'RuleError', 'require',
    'balance_limits', 'default_roles', 'validate_settings', 'settings_catalog',
    'players', 'alive', 'log', 'new_state', 'join', 'transfer_host',
    'finish', 'check_win', 'remove_players', 'enter_phase', 'start',
    'unique_target', 'resolve_phase', 'tick', 'action', 'snapshot',
]
