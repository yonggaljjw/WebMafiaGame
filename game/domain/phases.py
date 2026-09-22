"""낮 → 투표 → 밤의 단계 진행과 서버 타이머를 담당합니다."""
from collections import Counter
import secrets

from .rules import ACTIVE, default_roles, require, validate_settings
from .state import alive, check_win, finish, log, players, remove_players


def enter_phase(s, phase, now):
    """새 단계로 진입하며 마감 시각과 단계별 임시 선택을 초기화합니다."""
    s.update(
        phase=phase,
        deadline=now + s['durations'][phase],
        votes={},
        actions={},
        epoch=secrets.token_hex(8),
        paused=False,
    )
    if phase == 'day':
        s['round'] += 1
    label = {'day': '낮 토론', 'vote': '처형 투표', 'night': '밤 행동'}[phase]
    log(s, f"{s['round']}일차 · {label} 시간이 시작되었습니다.", now)


def start(s, uid, now):
    """준비 여부를 확인하고 역할을 섞은 뒤 첫 낮을 시작합니다."""
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
        # 업데이트 이전에 만들어진 방은 실제 참가 인원 기준 자동 배정을 유지합니다.
        counts = default_roles(n)

    roles = [role for role, count in counts.items() for _ in range(count)]
    secrets.SystemRandom().shuffle(roles)
    for p, role in zip(ps.values(), roles):
        p.update(role=role, alive=True, reports=[], ready=False)

    s.update(round=0, match=s['match'] + 1, winner=None, reason='', last_tick=now)
    enter_phase(s, 'day', now)


def unique_target(values):
    """최다 선택이 동률이면 None을 반환합니다. 임의 추첨은 하지 않습니다."""
    counts = Counter(values)
    if not counts:
        return None
    top = counts.most_common()
    return top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None


def resolve_phase(s, now):
    """현재 단계의 결과를 확정하고 다음 단계로 넘깁니다."""
    living = alive(s)
    if s['phase'] == 'day':
        enter_phase(s, 'vote', now)
        return

    if s['phase'] == 'vote':
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
        return

    if s['phase'] == 'night':
        actions = {k: v for k, v in s['actions'].items() if k in living and v in living}
        attacks = [v for k, v in actions.items() if living[k]['role'] == 'mafia' and living[v]['role'] != 'mafia']
        victim = unique_target(attacks)
        saved = {v for k, v in actions.items() if living[k]['role'] == 'doctor'}

        # 경찰이 같은 밤에 죽더라도 이미 선택한 조사는 수행하고, 결과는 본인에게만 공개합니다.
        for k, v in actions.items():
            if living[k]['role'] == 'police':
                living[k]['reports'].append({
                    'round': s['round'],
                    'name': living[v]['name'],
                    'mafia': living[v]['role'] == 'mafia',
                })

        if victim and victim not in saved:
            s['players'][victim]['alive'] = False
            log(s, f"밤사이 {living[victim]['name']} 님이 사망했습니다. 역할은 비공개입니다.", now)
        else:
            log(s, '밤사이 사망자가 없습니다.', now)

        if not check_win(s, now):
            enter_phase(s, 'day', now)


def tick(s, now, stale=8, grace=30, clock_failure=15):
    """접속 끊김과 단계 시간 만료를 검사하는 서버 시계 함수입니다."""
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
        # 유예 중에는 실제 게임 시간을 소비하지 않도록 경과 시간을 마감 시각에 더합니다.
        s['deadline'] += gap
        s['paused'] = True
        return

    if s['paused']:
        s['deadline'] += gap
    s['paused'] = False

    if now >= s['deadline']:
        resolve_phase(s, now)
