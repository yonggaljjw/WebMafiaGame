"""핵심 규칙과 HTTP 권한을 검증합니다. 실제 MySQL 잠금 테스트는 맨 아래에 있습니다."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.test import SimpleTestCase, TestCase, TransactionTestCase, Client, override_settings
from django.db import connection, close_old_connections
from . import engine as e
from .models import Room, Guest


def state_of(n=6):
    s = e.new_state('0', '참가자0', 100)
    for i in range(1, n):
        e.join(s, str(i), f'참가자{i}', 100)
        s['players'][str(i)]['ready'] = True
    e.start(s, '0', 100)
    # 규칙 테스트는 무작위 배정과 분리하여 역할을 고정합니다.
    roles = ['mafia', 'doctor', 'police'] + ['citizen'] * (n - 3)
    for p, role in zip(s['players'].values(), roles):
        p['role'] = role
    return s

class EngineTests(SimpleTestCase):
    def test_role_distribution(self):
        for n in range(4, 13):
            s = e.new_state('0', '0', 100)
            for i in range(1,n):
                e.join(s,str(i),str(i),100); s['players'][str(i)]['ready']=True
            e.start(s,'0',100)
            roles=[p['role'] for p in s['players'].values()]
            self.assertEqual(roles.count('mafia'),1 if n<=6 else 2 if n<=9 else 3)
            self.assertEqual(roles.count('doctor'),1); self.assertEqual(roles.count('police'),1)

    def test_start_requires_ready_host_minimum(self):
        s=e.new_state('0','host',100)
        with self.assertRaises(e.RuleError):e.start(s,'0',100)
        for i in range(1,4):e.join(s,str(i),str(i),100)
        with self.assertRaises(e.RuleError):e.start(s,'0',100)
        with self.assertRaises(e.RuleError):e.start(s,'1',100)

    def test_duplicate_nickname(self):
        s=e.new_state('0','Alice',100)
        with self.assertRaises(e.RuleError):e.join(s,'1','alice',100)

    def test_day_to_vote(self):
        s=state_of();e.resolve_phase(s,190);self.assertEqual(s['phase'],'vote')

    def test_majority_executes_and_town_wins(self):
        s=state_of();e.enter_phase(s,'vote',101)
        s['votes']={str(i):'0' for i in range(1,5)}
        e.resolve_phase(s,131)
        self.assertEqual(s['winner'],'town')

    def test_tie_and_nonmajority_do_not_execute(self):
        for votes in [{'0':'1','1':'0'}, {'1':'0','2':'0','3':'0'}]:
            s=state_of();e.enter_phase(s,'vote',101);s['votes']=votes
            e.resolve_phase(s,131)
            self.assertEqual(len(e.alive(s)),6);self.assertEqual(s['phase'],'night')

    def test_vote_replaces_not_accumulates(self):
        s=state_of();e.enter_phase(s,'vote',101)
        for target in ['0','1','2']:
            e.action(s,'3','vote',{'target':target,'epoch':s['epoch']},102)
        self.assertEqual(s['votes'],{'3':'2'})

    def test_old_epoch_rejected(self):
        s=state_of();old=s['epoch'];e.enter_phase(s,'vote',101)
        with self.assertRaises(e.RuleError):e.action(s,'3','vote',{'target':'0','epoch':old},102)

    def test_night_doctor_saves_and_police_reports(self):
        s=state_of();e.enter_phase(s,'night',101)
        s['actions']={'0':'3','1':'3','2':'0'};e.resolve_phase(s,131)
        self.assertTrue(s['players']['3']['alive'])
        self.assertTrue(s['players']['2']['reports'][0]['mafia'])
        self.assertEqual(s['phase'],'day')

    def test_doctor_can_save_self(self):
        s=state_of();e.enter_phase(s,'night',101)
        e.action(s,'1','ability',{'target':'1','epoch':s['epoch']},102)
        s['actions']['0']='1';e.resolve_phase(s,131)
        self.assertTrue(s['players']['1']['alive'])

    def test_night_kill_and_police_same_night_result(self):
        s=state_of();e.enter_phase(s,'night',101)
        s['actions']={'0':'2','2':'0'};e.resolve_phase(s,131)
        self.assertFalse(s['players']['2']['alive']);self.assertTrue(s['players']['2']['reports'][0]['mafia'])

    def test_mafia_tie_does_not_kill(self):
        s=state_of(8);s['players']['7']['role']='mafia';e.enter_phase(s,'night',101)
        s['actions']={'0':'3','7':'4'};e.resolve_phase(s,131)
        self.assertEqual(len(e.alive(s)),8)

    def test_mafia_cannot_attack_mafia_police_cannot_self(self):
        s=state_of();e.enter_phase(s,'night',101)
        for uid,target in [('0','0'),('2','2')]:
            with self.assertRaises(e.RuleError):e.action(s,uid,'ability',{'target':target,'epoch':s['epoch']},102)

    def test_no_action_means_no_kill(self):
        s=state_of();e.enter_phase(s,'night',101);e.resolve_phase(s,131)
        self.assertEqual(len(e.alive(s)),6)

    def test_dead_actions_rejected(self):
        s=state_of();s['players']['3']['alive']=False;e.enter_phase(s,'vote',101)
        with self.assertRaises(e.RuleError):e.action(s,'3','vote',{'target':'0','epoch':s['epoch']},102)

    def test_mafia_win_at_parity(self):
        s=state_of(4)
        s['players']['2']['alive']=s['players']['3']['alive']=False
        self.assertTrue(e.check_win(s,101));self.assertEqual(s['winner'],'mafia')

    def test_night_chat_restricted_even_for_dead_mafia(self):
        s=state_of();e.enter_phase(s,'night',101)
        for uid in ['1','2','3']:
            with self.assertRaises(e.RuleError):e.action(s,uid,'chat',{'text':'secret'},102)
        e.action(s,'0','chat',{'text':'secret'},102)
        self.assertEqual(s['messages'][-1]['channel'],'mafia')
        s['players']['0']['alive']=False
        with self.assertRaises(e.RuleError):e.action(s,'0','chat',{'text':'secret'},104)

    def test_private_information_absent(self):
        s=state_of();e.enter_phase(s,'night',101)
        e.action(s,'0','chat',{'text':'TOPSECRET'},102)
        s['players']['2']['reports']=[{'round':1,'name':'참가자0','mafia':True}]
        s['actions']={'0':'3'}
        view=e.snapshot(s,'3',103)
        self.assertNotIn('TOPSECRET',json.dumps(view))
        self.assertEqual(view['reports'],[]);self.assertEqual(view['mafia_actions'],{})
        self.assertIsNone(view['players'][0]['role'])
        self.assertEqual(e.snapshot(s,'0',103)['mafia_actions'],{'0':'3'})

    def test_ghost_chat_is_private(self):
        s=state_of();s['players']['3']['alive']=False
        e.action(s,'3','chat',{'text':'GHOSTONLY'},102)
        self.assertNotIn('GHOSTONLY',json.dumps(e.snapshot(s,'1',103)))
        self.assertIn('GHOSTONLY',json.dumps(e.snapshot(s,'3',103)))

    def test_departure_continues_when_balanced(self):
        s=state_of();e.remove_players(s,['3'],102)
        self.assertEqual(s['phase'],'day');self.assertEqual(len(e.alive(s)),5)

    def test_departure_cancels_if_mafia_gone_or_too_few(self):
        for n,uid in [(6,'0'),(4,'3')]:
            s=state_of(n);e.remove_players(s,[uid],102)
            self.assertEqual(s['winner'],'cancelled')

    def test_simultaneous_disconnect_cancels_without_order_bias(self):
        s=state_of();e.remove_players(s,['0','1','2'],102)
        self.assertEqual(s['winner'],'cancelled')

    def test_dead_departure_does_not_cancel_three_person_game(self):
        s=state_of(4);s['players']['3']['alive']=False
        e.remove_players(s,['3'],102);self.assertEqual(s['phase'],'day')

    def test_host_transfer(self):
        s=e.new_state('0','host',100);e.join(s,'1','next',100)
        e.remove_players(s,['0'],102);self.assertEqual(s['host'],'1')

    def test_disconnect_pauses_and_reconnect_restores_time(self):
        s=state_of();original=s['deadline']
        for t in range(101,111):
            for uid,p in s['players'].items():
                if uid!='3':p['last_seen']=t
            e.tick(s,t)
        self.assertTrue(s['paused']);self.assertGreater(s['deadline'],original)
        s['players']['3']['last_seen']=111
        e.tick(s,111);self.assertFalse(s['paused']);self.assertFalse(s['players']['3']['left'])

    def test_disconnect_expiration_continues(self):
        s=state_of()
        for t in range(101,131):
            for uid,p in s['players'].items():
                if uid!='3':p['last_seen']=t
            e.tick(s,t)
        self.assertTrue(s['players']['3']['left']);self.assertEqual(s['phase'],'day')

    def test_clock_failure_cancels(self):
        s=state_of();e.tick(s,116);self.assertEqual(s['winner'],'cancelled')

    def test_rematch_clears_roles_reports_and_messages(self):
        s=state_of();s['players']['2']['reports']=[{'mafia':True}]
        e.finish(s,'town','done',101);e.action(s,'0','rematch',{},102)
        self.assertEqual(s['phase'],'waiting')
        self.assertTrue(all(p['role'] is None and p['reports']==[] for p in s['players'].values()))
        self.assertEqual(len(s['messages']),1)

    def test_all_roles_reveal_only_on_end(self):
        s=state_of();e.finish(s,'town','done',101)
        self.assertTrue(all(p['role'] for p in e.snapshot(s,'3',102)['players']))

    def test_chat_length_and_throttle(self):
        s=state_of()
        with self.assertRaises(e.RuleError):e.action(s,'3','chat',{'text':'x'*301},102)
        e.action(s,'3','chat',{'text':'ok'},102)
        with self.assertRaises(e.RuleError):e.action(s,'3','chat',{'text':'again'},102.2)

    def test_chat_message_contains_sender_id_for_own_bubble(self):
        # 프런트가 닉네임 문자열이 아니라 실제 참가자 ID로 '내 채팅'을 구분합니다.
        s=state_of()
        e.action(s,'3','chat',{'text':'내 메시지'},102)
        self.assertEqual(s['messages'][-1]['sender_id'],'3')
        self.assertEqual(e.snapshot(s,'3',103)['messages'][-1]['sender_id'],'3')

    def test_malformed_target_rejected(self):
        s=state_of();e.enter_phase(s,'vote',101)
        with self.assertRaises(e.RuleError):e.action(s,'3','vote',{'target':{},'epoch':s['epoch']},102)


def fresh_client(enforce_csrf=False):
    client=Client(enforce_csrf_checks=enforce_csrf)
    client.get('/api/bootstrap')
    return client

def post(client,path,data):
    return client.post(path,json.dumps(data),content_type='application/json')

@override_settings(STORAGES={'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ApiTests(TestCase):
    def setUp(self):
        self.host=fresh_client()
        response=post(self.host,'/api/rooms/create',{'nickname':'방장','title':'테스트','capacity':4})
        self.assertEqual(response.status_code,201)
        self.code=response.json()['code']

    def test_home_renders(self):
        self.assertContains(self.host.get('/'),'MIDNIGHT')

    def test_csrf_required(self):
        c=fresh_client(True)
        self.assertEqual(post(c,'/api/rooms/create',{'nickname':'x','title':'x'}).status_code,403)

    def test_csrf_valid_cookie_accepted(self):
        c=fresh_client(True)
        response=c.post(f'/api/rooms/{self.code}/join',json.dumps({'nickname':'정상'}),content_type='application/json',HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value)
        self.assertEqual(response.status_code,200)

    def test_outsider_cannot_read_or_act(self):
        c=fresh_client()
        for endpoint in ['sync','action']:
            self.assertEqual(post(c,f'/api/rooms/{self.code}/{endpoint}',{'kind':'start'}).status_code,400)

    def test_capacity_enforced(self):
        for i in range(3):self.assertEqual(post(fresh_client(),f'/api/rooms/{self.code}/join',{'nickname':str(i)}).status_code,200)
        self.assertEqual(post(fresh_client(),f'/api/rooms/{self.code}/join',{'nickname':'extra'}).status_code,400)

    def test_guest_cannot_create_second_active_room(self):
        self.assertEqual(post(self.host,'/api/rooms/create',{'nickname':'x','title':'x'}).status_code,400)
        self.assertEqual(Room.objects.count(),1)

    def test_input_validation(self):
        c=fresh_client()
        for data in [[], {'nickname':'x','title':'x','capacity':True}, {'nickname':'x','title':'x','capacity':13}]:
            self.assertEqual(post(c,'/api/rooms/create',data).status_code,400)

    def test_malformed_action_kind_returns_400(self):
        for kind in [[], {}, None, 4]:
            self.assertEqual(post(self.host,f'/api/rooms/{self.code}/action',{'kind':kind}).status_code,400)

    def test_anonymous_separate_sessions(self):
        other=fresh_client()
        self.assertNotEqual(self.host.session['guest_id'],other.session['guest_id'])
        self.assertEqual(Guest.objects.count(),2)

    def test_reconnect_and_expiry(self):
        self.assertEqual(post(self.host,f'/api/rooms/{self.code}/sync',{}).status_code,200)
        r=Room.objects.get(pk=self.code);r.state['players'][self.host.session['guest_id']]['last_seen']=time.time()-31;r.save()
        response=post(self.host,f'/api/rooms/{self.code}/sync',{})
        self.assertEqual(response.status_code,410)
        self.assertIsNone(Guest.objects.get(pk=self.host.session['guest_id']).room_id)

    def test_complete_four_player_game(self):
        clients=[self.host]+[fresh_client() for _ in range(3)]
        for i,c in enumerate(clients[1:]):
            post(c,f'/api/rooms/{self.code}/join',{'nickname':f'참가{i}'})
            post(c,f'/api/rooms/{self.code}/action',{'kind':'ready','ready':True})
        response=post(self.host,f'/api/rooms/{self.code}/action',{'kind':'start'})
        self.assertEqual(response.json()['phase'],'day')
        room=Room.objects.get(pk=self.code)
        mafia=next(k for k,p in room.state['players'].items() if p['role']=='mafia')
        # 시간 경과는 DB 시계를 앞당겨 재현하고, HTTP 요청이 단 한 번 전환하게 합니다.
        room.state['deadline']=time.time()-1;room.save()
        view=post(self.host,f'/api/rooms/{self.code}/sync',{}).json()
        self.assertEqual(view['phase'],'vote')
        for c in clients:
            if c.session['guest_id']!=mafia:
                self.assertEqual(post(c,f'/api/rooms/{self.code}/action',{'kind':'vote','target':mafia,'epoch':view['epoch']}).status_code,200)
        room.refresh_from_db();room.state['deadline']=time.time()-1;room.save()
        result=post(self.host,f'/api/rooms/{self.code}/sync',{}).json()
        self.assertEqual(result['winner'],'town')
        self.assertTrue(all(p['role'] for p in result['players']))
        rematch=post(self.host,f'/api/rooms/{self.code}/action',{'kind':'rematch'}).json()
        self.assertEqual(rematch['phase'],'waiting')

    def test_lobby_excludes_private_data(self):
        data=self.host.get('/api/rooms').json()['rooms'][0]
        self.assertEqual(set(data),{'code','title','capacity','count'})


@skipUnless(connection.vendor=='mysql','실제 MySQL에서만 행 잠금의 동시성을 검증합니다.')
class MySQLConcurrencyTests(TransactionTestCase):
    def test_two_guests_race_for_last_slot(self):
        host=fresh_client()
        code=post(host,'/api/rooms/create',{'nickname':'host','title':'race','capacity':4}).json()['code']
        for i in range(2):post(fresh_client(),f'/api/rooms/{code}/join',{'nickname':f'early{i}'})
        clients=[fresh_client(),fresh_client()]
        def join_one(i):
            close_old_connections()
            try:return post(clients[i],f'/api/rooms/{code}/join',{'nickname':f'late{i}'}).status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(join_one,range(2)))
        self.assertEqual(sorted(statuses),[200,400])
        self.assertEqual(len(e.players(Room.objects.get(pk=code).state)),4)

class ConfiguredGameTests(SimpleTestCase):
    """설정이 단순 표시가 아니라 배정·타이머·재경기에 적용되는지 검증합니다."""
    def configured(self, n=8, roles=None, times=None):
        config=e.validate_settings(n,roles,times)
        s=e.new_state('0','host',100,game_settings=config)
        for i in range(1,n):
            e.join(s,str(i),f'p{i}',100)
            s['players'][str(i)]['ready']=True
        return s

    def test_configured_role_counts_for_all_sizes(self):
        from collections import Counter
        for n in range(4,13):
            limits=e.balance_limits(n)
            roles={'mafia':limits['mafia'],'police':0,'doctor':limits['doctor'],
                   'citizen':n-limits['mafia']-limits['doctor']}
            s=self.configured(n,roles)
            e.start(s,'0',100)
            actual=Counter(p['role'] for p in e.players(s).values())
            self.assertEqual({r:actual[r] for r in e.ROLE_NAMES},roles)

    def test_configured_durations_drive_each_phase(self):
        times={'day':47,'vote':19,'night':23}
        s=self.configured(times=times);e.start(s,'0',100)
        self.assertEqual(s['deadline'],147)
        e.resolve_phase(s,147);self.assertEqual(s['deadline'],166)
        e.resolve_phase(s,166);self.assertEqual(s['deadline'],189)
        e.resolve_phase(s,189);self.assertEqual(s['deadline'],236)

    def test_exact_participant_count_required(self):
        s=self.configured()
        del s['players']['7']
        with self.assertRaises(e.RuleError):e.start(s,'0',100)
        self.assertEqual(s['phase'],'waiting')
        self.assertTrue(all(p['role'] is None for p in e.players(s).values()))

    def test_role_caps_at_boundaries(self):
        self.assertEqual([e.balance_limits(n)['mafia'] for n in (6,7,9,10)],[1,2,2,3])
        self.assertEqual([e.balance_limits(n)['doctor'] for n in (7,8)],[1,2])
        self.assertEqual([e.balance_limits(n)['police'] for n in (9,10)],[1,2])

    def test_invalid_configurations_are_rejected(self):
        invalid=[
            (4,{'mafia':2,'police':0,'doctor':0,'citizen':2},None),
            (8,{'mafia':2,'police':2,'doctor':0,'citizen':4},None),
            (7,{'mafia':2,'police':0,'doctor':2,'citizen':3},None),
            (10,{'mafia':1,'police':2,'doctor':2,'citizen':5},None),
            (4,{'mafia':0,'police':1,'doctor':1,'citizen':2},None),
            (4,{'mafia':1,'police':1,'doctor':1,'citizen':0},None),
            (4,{'mafia':True,'police':1,'doctor':1,'citizen':1},None),
            (4,{'mafia':1.0,'police':1,'doctor':1,'citizen':1},None),
            (4,{'mafia':1,'police':1,'doctor':1,'citizen':2},None),
            (4,{'mafia':1},None),(4,[],None),
            (4,None,{'day':29,'vote':30,'night':30}),
            (4,None,{'day':301,'vote':30,'night':30}),
            (4,None,{'day':90,'vote':14,'night':30}),
            (4,None,{'day':90,'vote':121,'night':30}),
            (4,None,{'day':90,'vote':30,'night':14}),
            (4,None,{'day':90,'vote':30,'night':121}),
            (4,None,{'day':True,'vote':30,'night':30}),
        ]
        for n,roles,times in invalid:
            with self.subTest(roles=roles,times=times):
                with self.assertRaises(e.RuleError):e.validate_settings(n,roles,times)

    def test_time_boundaries_accepted(self):
        for times in [{'day':30,'vote':15,'night':15},{'day':300,'vote':120,'night':120}]:
            self.assertEqual(e.validate_settings(4,durations=times)['durations'],times)

    def test_start_revalidates_saved_configuration(self):
        s=self.configured()
        s['settings']['roles']['mafia']=8
        with self.assertRaises(e.RuleError):e.start(s,'0',100)
        self.assertEqual(s['phase'],'waiting')

    def test_rematch_retains_settings_and_reuses_them(self):
        from copy import deepcopy
        s=self.configured(times={'day':61,'vote':27,'night':39})
        expected=deepcopy(s['settings'])
        e.start(s,'0',100);e.finish(s,'town','end',101);e.action(s,'0','rematch',{},102)
        self.assertEqual(s['settings'],expected)
        for p in s['players'].values():p['ready']=True;p['last_seen']=103
        e.start(s,'0',103)
        self.assertEqual(s['deadline'],164)
        self.assertEqual(sum(p['role']=='mafia' for p in e.players(s).values()),2)

    def test_multiple_doctors_protect_different_targets(self):
        s=self.configured(8,{'mafia':2,'doctor':2,'police':0,'citizen':4})
        e.start(s,'0',100)
        mafia=[k for k,p in e.alive(s).items() if p['role']=='mafia']
        doctors=[k for k,p in e.alive(s).items() if p['role']=='doctor']
        citizens=[k for k,p in e.alive(s).items() if p['role']=='citizen']
        e.enter_phase(s,'night',101)
        s['actions']={mafia[0]:citizens[0],mafia[1]:citizens[0],doctors[0]:citizens[1],doctors[1]:citizens[0]}
        e.resolve_phase(s,131)
        self.assertEqual(len(e.alive(s)),8)

    def test_multiple_police_keep_reports_private(self):
        s=self.configured(10,{'mafia':3,'doctor':1,'police':2,'citizen':4})
        e.start(s,'0',100)
        cops=[k for k,p in e.alive(s).items() if p['role']=='police']
        mafia=next(k for k,p in e.alive(s).items() if p['role']=='mafia')
        citizen=next(k for k,p in e.alive(s).items() if p['role']=='citizen')
        e.enter_phase(s,'night',101);s['actions']={cops[0]:mafia,cops[1]:citizen}
        e.resolve_phase(s,131)
        first=e.snapshot(s,cops[0],131);second=e.snapshot(s,cops[1],131)
        self.assertEqual(len(first['reports']),1);self.assertTrue(first['reports'][0]['mafia'])
        self.assertEqual(len(second['reports']),1);self.assertFalse(second['reports'][0]['mafia'])
        self.assertIsNone(next(p for p in first['players'] if p['id']==cops[1])['role'])


class ConfiguredApiTests(TestCase):
    def test_bootstrap_exposes_server_balance_catalog(self):
        c=fresh_client();catalog=c.get('/api/bootstrap').json()['settings_catalog']
        self.assertEqual(catalog['by_players']['8']['limits']['doctor'],2)
        self.assertEqual(catalog['by_players']['9']['limits']['police'],1)
        self.assertEqual(catalog['time_limits']['day'],[30,300])

    def test_http_settings_persist_apply_and_insufficient_start_fails(self):
        from collections import Counter
        clients=[fresh_client() for _ in range(4)]
        roles={'mafia':1,'doctor':1,'police':0,'citizen':2}
        response=post(clients[0],'/api/rooms/create',{'nickname':'host','title':'custom','capacity':4,
                      'role_counts':roles,'day_seconds':47,'vote_seconds':19,'night_seconds':23})
        self.assertEqual(response.status_code,201)
        code=response.json()['code']
        self.assertEqual(response.json()['settings']['roles'],roles)
        for i,c in enumerate(clients[1:]):
            view=post(c,f'/api/rooms/{code}/join',{'nickname':f'p{i}'}).json()
            self.assertEqual(view['settings']['roles'],roles)
            post(c,f'/api/rooms/{code}/action',{'kind':'ready','ready':True})
        started=post(clients[0],f'/api/rooms/{code}/action',{'kind':'start'}).json()
        self.assertEqual(round(started['deadline']-started['server_time']),47)
        r=Room.objects.get(pk=code)
        counts=Counter(p['role'] for p in e.players(r.state).values())
        self.assertEqual({role:counts[role] for role in roles},roles)
        for phase,seconds in [('vote',19),('night',23),('day',47)]:
            r.refresh_from_db();r.state['deadline']=time.time()-1;r.save()
            view=post(clients[0],f'/api/rooms/{code}/sync',{}).json()
            self.assertEqual(view['phase'],phase)
            self.assertEqual(round(view['deadline']-view['server_time']),seconds)

    def test_all_ready_but_below_configured_size_rejected(self):
        host=fresh_client()
        code=post(host,'/api/rooms/create',{'nickname':'host','title':'eight','capacity':8}).json()['code']
        for i in range(3):
            c=fresh_client();post(c,f'/api/rooms/{code}/join',{'nickname':f'p{i}'})
            post(c,f'/api/rooms/{code}/action',{'kind':'ready','ready':True})
        self.assertEqual(post(host,f'/api/rooms/{code}/action',{'kind':'start'}).status_code,400)
        self.assertEqual(Room.objects.get(pk=code).status,'waiting')

    def test_api_rejects_tampered_configuration_without_creating_room(self):
        c=fresh_client()
        for extra in [{'vote_seconds':0},{'night_seconds':999},{'role_counts':{'mafia':3,'doctor':0,'police':0,'citizen':1}}]:
            response=post(c,'/api/rooms/create',{'nickname':'host','title':'bad','capacity':4,**extra})
            self.assertEqual(response.status_code,400)
        self.assertEqual(Room.objects.count(),0)
