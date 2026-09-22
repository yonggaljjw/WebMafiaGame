"""Room.state에서 현재 참가자에게 공개해도 되는 정보만 골라냅니다."""

from .rules import ACTIVE


def snapshot(s, uid, now, stale=8, grace=30):
    """화이트리스트 방식으로 참가자별 공개 상태를 만듭니다.

    CSS로 비밀 정보를 숨기는 것이 아니라 아예 JSON 응답에서 제거합니다.
    """
    me = s['players'][uid]
    ended = s['phase'] == 'ended'
    public_players = []

    for k, p in s['players'].items():
        visible_role = ended or k == uid or (me['role'] == 'mafia' and p['role'] == 'mafia')
        public_players.append({
            'id': k,
            'name': p['name'],
            'alive': p['alive'],
            'left': p['left'],
            'ready': p['ready'],
            'connected': now - p['last_seen'] < stale and not p['left'],
            'role': p['role'] if visible_role else None,
            'reconnect_seconds': max(0, round(grace - (now - p['last_seen']))) if not p['left'] else 0,
        })

    channels = {'public'}
    if me['role'] == 'mafia':
        channels.add('mafia')
    if not me['alive']:
        channels.add('ghost')

    chat_enabled = not s['paused'] and (
        s['phase'] != 'night' or (me['alive'] and me['role'] == 'mafia')
    )

    return {
        'settings': s.get('settings'),
        'durations': dict(s['durations']),
        'phase': s['phase'],
        'round': s['round'],
        'epoch': s['epoch'],
        'host': s['host'],
        'players': public_players,
        'me': uid,
        'deadline': s['deadline'],
        'server_time': now,
        'paused': s['paused'],
        'winner': s['winner'],
        'reason': s['reason'],
        'messages': [m for m in s['messages'] if m['channel'] in channels],
        'reports': me['reports'],
        'my_vote': s['votes'].get(uid),
        'voted': uid in s['votes'],
        'my_action': s['actions'].get(uid),
        'acted': uid in s['actions'],
        'chat_enabled': chat_enabled,
        'chat_channel': (
            'mafia'
            if s['phase'] == 'night'
            else 'ghost'
            if not me['alive'] and s['phase'] in ACTIVE
            else 'public'
        ),
        'mafia_actions': {
            k: v for k, v in s['actions'].items() if s['players'][k]['role'] == 'mafia'
        } if me['role'] == 'mafia' else {},
    }
