"""참가자가 보내는 ready/chat/vote/ability 같은 명령을 처리합니다."""
import secrets

from .phases import start
from .rules import ACTIVE, RuleError, require
from .state import alive, log, players, remove_players


def action(s, uid, kind, payload, now):
    """한 참가자의 행동을 검증하고 Room.state에 반영합니다."""
    p = s['players'].get(uid)
    require(p is not None and not p['left'], '이 방의 참가자가 아닙니다.')

    if kind == 'leave':
        remove_players(s, [uid], now)
        return

    if kind == 'ready':
        require(s['phase'] == 'waiting', '대기실에서만 준비할 수 있습니다.')
        require(isinstance(payload.get('ready'), bool), '준비 상태가 올바르지 않습니다.')
        p['ready'] = payload['ready']
        return

    if kind == 'start':
        start(s, uid, now)
        return

    if kind == 'rematch':
        require(uid == s['host'] and s['phase'] == 'ended', '종료 후 방장만 대기실로 전환할 수 있습니다.')
        s.update(
            players=players(s),
            phase='waiting',
            winner=None,
            reason='',
            round=0,
            votes={},
            actions={},
            deadline=None,
            epoch=secrets.token_hex(8),
            messages=[],
            sequence=0,
        )
        for member in s['players'].values():
            member.update(role=None, ready=False, alive=True, reports=[])
        log(s, '새 게임을 준비합니다.', now)
        return

    if kind == 'chat':
        text = payload.get('text', '')
        require(isinstance(text, str) and 1 <= len(text.strip()) <= 300, '메시지는 1~300자로 입력하세요.')
        require(now - p['last_chat'] >= 0.8, '메시지를 너무 빠르게 보내고 있습니다.')
        require(not s['paused'], '재접속 대기 중에는 채팅도 잠시 멈춥니다.')

        channel = 'public'
        if s['phase'] in ACTIVE:
            if s['phase'] == 'night':
                require(p['alive'] and p['role'] == 'mafia', '밤에는 생존 마피아만 대화할 수 있습니다.')
                channel = 'mafia'
            elif not p['alive']:
                channel = 'ghost'

        # sender_id까지 저장해야 같은 닉네임 문자열 비교가 아니라 실제 참가자 ID로
        # '내 메시지'를 식별하여 오른쪽 정렬할 수 있습니다.
        log(s, text.strip(), now, channel, p['name'], uid)
        p['last_chat'] = now
        return

    if kind in {'vote', 'ability'}:
        require(p['alive'] and not s['paused'], '생존 중이며 게임이 진행 중이어야 합니다.')
        # 이전 단계에서 보낸 요청이 늦게 도착해 현재 단계의 선택을 바꾸지 못하게 합니다.
        require(payload.get('epoch') == s['epoch'], '단계가 바뀌었습니다. 다시 선택하세요.')
        target = payload.get('target')
        require(target is None or isinstance(target, str), '대상이 올바르지 않습니다.')

        if kind == 'vote':
            require(s['phase'] == 'vote', '투표 시간이 아닙니다.')
            require(target is None or target in alive(s), '생존한 사람만 투표할 수 있습니다.')
            s['votes'][uid] = target
            return

        require(
            s['phase'] == 'night' and p['role'] in {'mafia', 'doctor', 'police'},
            '지금 사용할 수 있는 능력이 없습니다.',
        )
        require(target is None or target in alive(s), '생존한 사람만 선택할 수 있습니다.')
        if target:
            require(
                not (p['role'] == 'mafia' and s['players'][target]['role'] == 'mafia'),
                '동료 마피아는 공격할 수 없습니다.',
            )
            require(not (p['role'] == 'police' and target == uid), '자신은 조사할 수 없습니다.')
        s['actions'][uid] = target
        return

    raise RuleError('지원하지 않는 행동입니다.')
