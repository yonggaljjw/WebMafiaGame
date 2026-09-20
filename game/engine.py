"""게임 규칙만 담당하는 순수 Python 엔진.

HTTP·DB를 모르는 함수로 작성해 역할 배정, 승리 조건, 동시 이탈 등을
테스트하기 쉽습니다. 호출자는 반드시 방 행을 잠근 후 상태를 저장해야 합니다.
"""
from collections import Counter
import secrets

ACTIVE = {'day', 'vote', 'night'}
ROLE_NAMES = {'mafia': '마피아', 'doctor': '의사', 'police': '경찰', 'citizen': '시민'}

class RuleError(Exception):
    pass

def require(condition, message):
    if not condition:
        raise RuleError(message)

# 밸런스 정책을 한 곳에 둡니다. 브라우저도 bootstrap API로 이 값을 받아 씁니다.
# 승률을 보장하는 공식이 아니라, 작은 방의 마피아/특수직업 과밀을 막는 초기 규칙입니다.
TIME_LIMITS = {'day': (30, 300), 'vote': (15, 120), 'night': (15, 120)}

def balance_limits(n):
    require(type(n) is int and 4 <= n <= 12, '시작 인원은 4~12명입니다.')
    return {'mafia': (n - 1) // 3, 'police': 1 if n < 10 else 2,
            'doctor': 1 if n < 8 else 2, 'citizen': n - 1}

def default_roles(n):
    limits = balance_limits(n)
    return {'mafia': limits['mafia'], 'police': 1, 'doctor': 1,
            'citizen': n - limits['mafia'] - 2}

def validate_settings(n, roles=None, durations=None):
    """UI 우회 요청도 같은 기준으로 거절합니다. bool도 정수로 인정하지 않습니다."""
    limits = balance_limits(n)
    roles = default_roles(n) if roles is None else roles
    durations = {'day': 90, 'vote': 30, 'night': 30} if durations is None else durations
    require(isinstance(roles, dict) and set(roles) == set(ROLE_NAMES), '네 역할의 인원을 모두 지정하세요.')
    for role, value in roles.items():
        minimum = 1 if role in {'mafia', 'citizen'} else 0
        require(type(value) is int and minimum <= value <= limits[role],
                f'{ROLE_NAMES[role]}은 {minimum}~{limits[role]}명으로 설정하세요.')
    require(sum(roles.values()) == n, '역할 인원 합계는 시작 인원과 같아야 합니다.')
    require(roles['police'] + roles['doctor'] <= roles['mafia'] + 1,
            '경찰+의사는 마피아 수+1명 이하여야 합니다. 시민팀 특수직업 과밀을 제한합니다.')
    require(isinstance(durations, dict) and set(durations) == set(TIME_LIMITS), '세 단계의 시간을 모두 지정하세요.')
    for phase, value in durations.items():
        low, high = TIME_LIMITS[phase]
        require(type(value) is int and low <= value <= high, f'{phase} 시간은 {low}~{high}초의 정수여야 합니다.')
    # 입력 객체와 참조를 분리하여 호출자가 원본을 수정해도 저장 설정이 바뀌지 않게 합니다.
    return {'player_count': n, 'roles': dict(roles), 'durations': dict(durations)}

def settings_catalog():
    return {'by_players': {str(n): {'limits': balance_limits(n), 'defaults': default_roles(n)}
                           for n in range(4, 13)},
            'time_limits': TIME_LIMITS, 'special_extra': 1}

def players(s):
    return {k: p for k, p in s['players'].items() if not p['left']}

def alive(s):
    return {k: p for k, p in players(s).items() if p['alive']}

def log(s, text, now, channel='public', sender=None):
    s['sequence'] += 1
    s['messages'].append({'id': f"{s['match']}:{s['sequence']}", 'text': text, 'time': now, 'system': sender is None,
                          'channel': channel, 'sender': sender or '시스템'})
    # 한 방의 JSON 크기가 무한히 커지지 않도록 최신 메시지만 보관합니다.
    s['messages'] = s['messages'][-200:]

def new_state(host, nickname, now, day_seconds=90, vote_seconds=30, night_seconds=30, game_settings=None):
    s = {'host': host, 'phase': 'waiting', 'round': 0, 'epoch': secrets.token_hex(8),
         'players': {}, 'messages': [], 'sequence': 0, 'deadline': None,
         'durations': {'day': day_seconds, 'vote': vote_seconds, 'night': night_seconds},
         'votes': {}, 'actions': {}, 'last_tick': now, 'paused': False,
         'winner': None, 'reason': '', 'match': 0}
    if game_settings is not None:
        checked = validate_settings(game_settings['player_count'], game_settings['roles'], game_settings['durations'])
        s['settings'] = checked
        s['durations'] = dict(checked['durations'])
    join(s, host, nickname, now)
    return s

def join(s, uid, nickname, now):
    require(s['phase'] == 'waiting', '이미 시작한 방에는 입장할 수 없습니다.')
    require(all(p['name'].casefold() != nickname.casefold() for p in players(s).values()), '방 안에서 이미 사용 중인 닉네임입니다.')
    s['players'][uid] = {'name': nickname, 'alive': True, 'role': None, 'ready': False,
                         'last_seen': now, 'left': False, 'reports': [], 'last_chat': 0}
    log(s, f'{nickname} 님이 입장했습니다.', now)

def transfer_host(s, now):
    if s['host'] not in players(s):
        s['host'] = next(iter(players(s)), None)
        if s['host']:
            log(s, f"{s['players'][s['host']]['name']} 님이 방장을 이어받았습니다.", now)

def finish(s, winner, reason, now):
    s.update(phase='ended', winner=winner, reason=reason, deadline=None, paused=False,
             epoch=secrets.token_hex(8))
    log(s, reason, now)

def check_win(s, now):
    living = alive(s)
    mafia = sum(p['role'] == 'mafia' for p in living.values())
    town = len(living) - mafia
    if mafia == 0:
        finish(s, 'town', '시민팀 승리! 모든 마피아를 찾아냈습니다.', now)
    elif mafia >= town:
        finish(s, 'mafia', '마피아팀 승리! 생존 마피아가 시민팀 이상입니다.', now)
    return s['phase'] == 'ended'

def remove_players(s, uids, now):
    """동시에 끊긴 사람을 한꺼번에 제외하고 검사해야 판정 순서의 편향이 없습니다."""
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
        # 이탈로 진영이 없어지거나 즉시 승패가 결정되는 상황은 기권승 대신 무효입니다.
        if len(living) < 4 or mafia == 0 or mafia >= town:
            finish(s, 'cancelled', '참가자 이탈로 진행 조건을 충족하지 못해 무효 종료합니다.', now)
        else:
            log(s, '이탈자를 제외해도 양 진영·4인 이상이 유지되어 게임을 계속합니다.', now)

def enter_phase(s, phase, now):
    s.update(phase=phase, deadline=now + s['durations'][phase], votes={}, actions={},
             epoch=secrets.token_hex(8), paused=False)
    if phase == 'day':
        s['round'] += 1
    label = {'day': '낮 토론', 'vote': '처형 투표', 'night': '밤 행동'}[phase]
    log(s, f"{s['round']}일차 · {label} 시간이 시작되었습니다.", now)

def start(s, uid, now):
    require(uid == s['host'], '방장만 시작할 수 있습니다.')
    require(s['phase'] == 'waiting', '대기 중일 때만 시작할 수 있습니다.')
    ps = players(s)
    require(4 <= len(ps) <= 12, '게임 시작에는 4~12명이 필요합니다.')
    require(all(now - p['last_seen'] < 8 for p in ps.values()), '모두 연결되어 있어야 합니다.')
    require(all(p['ready'] or k == uid for k, p in ps.items()), '모든 참가자가 준비를 눌러야 합니다.')
    n = len(ps)
    if 'settings' in s:
        config = s['settings']
        require(n == config['player_count'], f"설정한 {config['player_count']}명이 모두 모여야 시작할 수 있습니다.")
        checked = validate_settings(n, config['roles'], config['durations'])
        counts = checked['roles']
        s['durations'] = dict(checked['durations'])
    else:
        # 업데이트 전 생성된 방은 기존의 실제 참가 인원 기준 자동 배정을 유지합니다.
        counts = default_roles(n)
    roles = [role for role, count in counts.items() for _ in range(count)]
    secrets.SystemRandom().shuffle(roles)
    for p, role in zip(ps.values(), roles):
        p.update(role=role, alive=True, reports=[], ready=False)
    s.update(round=0, match=s['match'] + 1, winner=None, reason='', last_tick=now)
    enter_phase(s, 'day', now)

def unique_target(values):
    """최다 선택이 동률이면 None: 투표와 마피아 공격 모두 임의 추첨하지 않습니다."""
    counts = Counter(values)
    if not counts:
        return None
    top = counts.most_common()
    return top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None

def resolve_phase(s, now):
    living = alive(s)
    if s['phase'] == 'day':
        enter_phase(s, 'vote', now)
    elif s['phase'] == 'vote':
        votes = [v for k, v in s['votes'].items() if k in living and v in living]
        victim = unique_target(votes)
        tally = Counter(votes)
        if tally:
            log(s, '투표 결과: ' + ', '.join(f"{living[k]['name']} {n}표" for k, n in tally.items()), now)
        if victim and tally[victim] > len(living) / 2:
            s['players'][victim]['alive'] = False
            log(s, f"{living[victim]['name']} 님이 과반수 투표로 처형되었습니다. 역할은 비공개입니다.", now)
        else:
            log(s, '과반수 미달 또는 동률로 처형하지 않습니다.', now)
        if not check_win(s, now):
            enter_phase(s, 'night', now)
    elif s['phase'] == 'night':
        actions = {k: v for k, v in s['actions'].items() if k in living and v in living}
        attacks = [v for k, v in actions.items() if living[k]['role'] == 'mafia' and living[v]['role'] != 'mafia']
        victim = unique_target(attacks)
        saved = {v for k, v in actions.items() if living[k]['role'] == 'doctor'}
        # 경찰이 같은 밤에 사망해도 선택한 조사는 수행됩니다. 결과는 본인만 봅니다.
        for k, v in actions.items():
            if living[k]['role'] == 'police':
                living[k]['reports'].append({'round': s['round'], 'name': living[v]['name'],
                                              'mafia': living[v]['role'] == 'mafia'})
        if victim and victim not in saved:
            s['players'][victim]['alive'] = False
            log(s, f"밤사이 {living[victim]['name']} 님이 사망했습니다. 역할은 비공개입니다.", now)
        else:
            log(s, '밤사이 사망자가 없습니다.', now)
        if not check_win(s, now):
            enter_phase(s, 'day', now)

def tick(s, now, stale=8, grace=30, clock_failure=15):
    """독립 clock 프로세스와 요청 모두 호출합니다. 방 잠금으로 전환은 한 번만 됩니다."""
    gap = max(0, now - s['last_tick'])
    s['last_tick'] = now
    if s['phase'] in ACTIVE and gap > clock_failure:
        finish(s, 'cancelled', '서버 진행 확인이 지연되어 공정한 판정이 불가능합니다. 무효 종료합니다.', now)
    expired = [k for k, p in players(s).items() if now - p['last_seen'] >= grace]
    if expired:
        remove_players(s, expired, now)
    if s['phase'] not in ACTIVE:
        return
    missing = [p for p in alive(s).values() if now - p['last_seen'] >= stale]
    if missing:
        # 유예 중에는 토론/행동 시간을 소모하지 않습니다. 귀환 직후도 마지막 구간을 보상합니다.
        s['deadline'] += gap
        s['paused'] = True
        return
    if s['paused']:
        s['deadline'] += gap
    s['paused'] = False
    if now >= s['deadline']:
        resolve_phase(s, now)

def action(s, uid, kind, payload, now):
    p = s['players'].get(uid)
    require(p is not None and not p['left'], '이 방의 참가자가 아닙니다.')
    if kind == 'leave':
        remove_players(s, [uid], now)
        return
    if kind == 'ready':
        require(s['phase'] == 'waiting', '대기실에서만 준비할 수 있습니다.')
        require(isinstance(payload.get('ready'), bool), '준비 상태가 올바르지 않습니다.')
        p['ready'] = payload['ready']
    elif kind == 'start':
        start(s, uid, now)
    elif kind == 'rematch':
        require(uid == s['host'] and s['phase'] == 'ended', '종료 후 방장만 대기실로 전환할 수 있습니다.')
        s.update(players=players(s), phase='waiting', winner=None, reason='', round=0,
                 votes={}, actions={}, deadline=None, epoch=secrets.token_hex(8), messages=[], sequence=0)
        for member in s['players'].values():
            member.update(role=None, ready=False, alive=True, reports=[])
        log(s, '새 게임을 준비합니다.', now)
    elif kind == 'chat':
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
        log(s, text.strip(), now, channel, p['name'])
        p['last_chat'] = now
    elif kind in {'vote', 'ability'}:
        require(p['alive'] and not s['paused'], '생존 중이며 게임이 진행 중이어야 합니다.')
        # 지난 낮/밤에 보낸 요청이 늦게 도착해 새 턴의 행동을 바꾸는 것을 막습니다.
        require(payload.get('epoch') == s['epoch'], '단계가 바뀌었습니다. 다시 선택하세요.')
        target = payload.get('target')
        require(target is None or isinstance(target, str), '대상이 올바르지 않습니다.')
        if kind == 'vote':
            require(s['phase'] == 'vote', '투표 시간이 아닙니다.')
            require(target is None or target in alive(s), '생존한 사람만 투표할 수 있습니다.')
            s['votes'][uid] = target
        else:
            require(s['phase'] == 'night' and p['role'] in {'mafia', 'doctor', 'police'}, '지금 사용할 수 있는 능력이 없습니다.')
            require(target is None or target in alive(s), '생존한 사람만 선택할 수 있습니다.')
            if target:
                require(not (p['role'] == 'mafia' and s['players'][target]['role'] == 'mafia'), '동료 마피아는 공격할 수 없습니다.')
                require(not (p['role'] == 'police' and target == uid), '자신은 조사할 수 없습니다.')
            s['actions'][uid] = target
    else:
        raise RuleError('지원하지 않는 행동입니다.')

def snapshot(s, uid, now, stale=8, grace=30):
    """화이트리스트 방식 직렬화: 비밀 역할/상대 투표/경찰 결과는 응답에서 제거합니다."""
    me = s['players'][uid]
    ended = s['phase'] == 'ended'
    public_players = []
    for k, p in s['players'].items():
        visible_role = ended or k == uid or (me['role'] == 'mafia' and p['role'] == 'mafia')
        public_players.append({'id': k, 'name': p['name'], 'alive': p['alive'], 'left': p['left'],
            'ready': p['ready'], 'connected': now - p['last_seen'] < stale and not p['left'],
            'role': p['role'] if visible_role else None,
            'reconnect_seconds': max(0, round(grace - (now - p['last_seen']))) if not p['left'] else 0})
    channels = {'public'}
    if me['role'] == 'mafia':
        channels.add('mafia')
    if not me['alive']:
        channels.add('ghost')
    chat_enabled = not s['paused'] and (s['phase'] != 'night' or (me['alive'] and me['role'] == 'mafia'))
    return {'settings': s.get('settings'), 'durations': dict(s['durations']),
            'phase': s['phase'], 'round': s['round'], 'epoch': s['epoch'], 'host': s['host'],
            'players': public_players, 'me': uid, 'deadline': s['deadline'], 'server_time': now,
            'paused': s['paused'], 'winner': s['winner'], 'reason': s['reason'],
            'messages': [m for m in s['messages'] if m['channel'] in channels],
            'reports': me['reports'], 'my_vote': s['votes'].get(uid),
            'voted': uid in s['votes'], 'my_action': s['actions'].get(uid),
            'acted': uid in s['actions'], 'chat_enabled': chat_enabled,
            'chat_channel': 'mafia' if s['phase'] == 'night' else 'ghost' if not me['alive'] and s['phase'] in ACTIVE else 'public',
            'mafia_actions': {k: v for k, v in s['actions'].items() if s['players'][k]['role'] == 'mafia'} if me['role'] == 'mafia' else {}}
