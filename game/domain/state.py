"""방 상태(JSON)의 생성·조회·참가자 관리·공통 로그를 담당합니다.

Room.state 안의 자료구조를 직접 다루는 코드를 한 곳에 모아 두었습니다.
HTTP나 ORM을 사용하지 않으므로 일반 Python 객체만으로 단위 테스트할 수 있습니다.
"""
import secrets

from .rules import ACTIVE, require, validate_settings


def players(s):
    """퇴장하지 않은 참가자만 반환합니다."""
    return {k: p for k, p in s['players'].items() if not p['left']}


def alive(s):
    """현재 방에 남아 있으면서 생존한 참가자만 반환합니다."""
    return {k: p for k, p in players(s).items() if p['alive']}


def log(s, text, now, channel='public', sender=None, sender_id=None):
    """시스템/채팅 메시지를 방 상태에 기록합니다.

    sender_id는 '이 메시지가 내 것인가?'를 UI가 정확히 판단하기 위한 값입니다.
    화면에는 노출해도 되는 익명 Guest UUID만 들어가며, 인증은 여전히 세션으로 처리합니다.
    """
    s['sequence'] += 1
    s['messages'].append({
        'id': f"{s['match']}:{s['sequence']}",
        'text': text,
        'time': now,
        'system': sender is None,
        'channel': channel,
        'sender': sender or '시스템',
        'sender_id': sender_id,
    })
    # 한 방의 JSON 크기가 무한히 커지지 않도록 최신 200개만 유지합니다.
    s['messages'] = s['messages'][-200:]


def new_state(host, nickname, now, day_seconds=90, vote_seconds=30, night_seconds=30, game_settings=None):
    """새 방의 초기 Room.state 값을 만듭니다."""
    s = {
        'host': host,
        'phase': 'waiting',
        'round': 0,
        'epoch': secrets.token_hex(8),
        'players': {},
        'messages': [],
        'sequence': 0,
        'deadline': None,
        'durations': {'day': day_seconds, 'vote': vote_seconds, 'night': night_seconds},
        'votes': {},
        'actions': {},
        'last_tick': now,
        'paused': False,
        'winner': None,
        'reason': '',
        'match': 0,
    }
    if game_settings is not None:
        checked = validate_settings(
            game_settings['player_count'],
            game_settings['roles'],
            game_settings['durations'],
        )
        s['settings'] = checked
        s['durations'] = dict(checked['durations'])
    join(s, host, nickname, now)
    return s


def join(s, uid, nickname, now):
    """대기 중인 방에 참가자를 추가합니다."""
    require(s['phase'] == 'waiting', '이미 시작한 방에는 입장할 수 없습니다.')
    require(
        all(p['name'].casefold() != nickname.casefold() for p in players(s).values()),
        '방 안에서 이미 사용 중인 닉네임입니다.',
    )
    s['players'][uid] = {
        'name': nickname,
        'alive': True,
        'role': None,
        'ready': False,
        'last_seen': now,
        'left': False,
        'reports': [],
        'last_chat': 0,
    }
    log(s, f'{nickname} 님이 입장했습니다.', now)


def transfer_host(s, now):
    """기존 방장이 나갔다면 남은 사람 중 첫 참가자에게 방장을 넘깁니다."""
    if s['host'] not in players(s):
        s['host'] = next(iter(players(s)), None)
        if s['host']:
            log(s, f"{s['players'][s['host']]['name']} 님이 방장을 이어받았습니다.", now)


def finish(s, winner, reason, now):
    """게임을 종료 상태로 전환하고 종료 사유를 시스템 메시지로 남깁니다."""
    s.update(
        phase='ended',
        winner=winner,
        reason=reason,
        deadline=None,
        paused=False,
        epoch=secrets.token_hex(8),
    )
    log(s, reason, now)


def check_win(s, now):
    """현재 생존 인원으로 승패를 판정합니다."""
    living = alive(s)
    mafia = sum(p['role'] == 'mafia' for p in living.values())
    town = len(living) - mafia
    if mafia == 0:
        finish(s, 'town', '시민팀 승리! 모든 마피아를 찾아냈습니다.', now)
    elif mafia >= town:
        finish(s, 'mafia', '마피아팀 승리! 생존 마피아가 시민팀 이상입니다.', now)
    return s['phase'] == 'ended'


def remove_players(s, uids, now):
    """여러 이탈자를 한 번에 반영하고 게임 지속 가능 여부를 검사합니다."""
    removed_alive = False
    for uid in uids:
        p = s['players'].get(uid)
        if not p or p['left']:
            continue
        removed_alive |= p['alive']
        p.update(left=True, alive=False)
        log(s, f"{p['name']} 님이 퇴장했습니다.", now)
        if s['phase'] == 'waiting':
            del s['players'][uid]

    transfer_host(s, now)
    if not players(s):
        s.update(phase='closed', deadline=None, paused=False)
        return

    if s['phase'] in ACTIVE and removed_alive:
        living = alive(s)
        mafia = sum(p['role'] == 'mafia' for p in living.values())
        town = len(living) - mafia
        # 이탈 자체로 승패가 정해지는 상황은 기권승이 아니라 무효 경기로 처리합니다.
        if len(living) < 4 or mafia == 0 or mafia >= town:
            finish(s, 'cancelled', '참가자 이탈로 진행 조건을 충족하지 못해 무효 종료합니다.', now)
        else:
            log(s, '이탈자를 제외해도 양 진영·4인 이상이 유지되어 게임을 계속합니다.', now)
