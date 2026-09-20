/* 화면은 서버가 내려준 공개 상태만 그립니다.
 * 역할 판정·승패 계산·채팅 권한 확인은 전부 Python 서버에서 다시 검사합니다.
 * WebSocket 대신 겹치지 않는 1초 폴링을 사용하여 별도 Redis 없이 동기화합니다.
 */
'use strict';
const $ = id => document.getElementById(id);
const roleNames = {mafia:'마피아', doctor:'의사', police:'경찰', citizen:'시민'};
const phaseNames = {waiting:'참가자를 기다리는 중', day:'낮 · 의심을 나눌 시간', vote:'투표 · 당신의 선택은?', night:'밤 · 도시가 잠듭니다', ended:'게임 종료'};
const descriptions = {mafia:'동료와 대화해 밤의 공격 대상을 정하세요. 생존 마피아가 시민팀 이상이 되면 승리합니다.', doctor:'밤마다 한 사람을 보호하세요. 자신을 보호할 수도 있습니다. 마피아를 모두 처치하면 승리합니다.', police:'밤마다 한 사람을 조사하세요. 마피아 여부는 밤이 끝난 뒤 나에게만 공개됩니다.', citizen:'말의 빈틈을 찾고 투표하세요. 마피아를 모두 처치하면 승리합니다.'};
let code = null, state = null, generation = 0, serverOffset = 0, pollTimer;
let lastLobby = '', lastMessages = '', lastRoster = '', lastTargets = '', lastControls = '', lastReports = '';
let localNickname = '', networkIssue = false, settingsCatalog = null;
try { localNickname = localStorage.getItem('midnight-nickname') || ''; } catch (_) { /* 저장소가 막혀도 플레이 가능합니다. */ }
$('nickname').value = localNickname;
function showError(message) { $('notice').textContent = message; $('notice').hidden = false; }
function clearError() { $('notice').hidden = true; }
function connection(ok) { if(ok && networkIssue) { clearError(); networkIssue = false; } $('network').textContent = ok ? '온라인' : '재연결 중'; $('network').classList.toggle('offline', !ok); }
function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text; // 사용자 입력에 innerHTML을 사용하지 않아 XSS를 막습니다.
  return el;
}
function csrf() {
  return document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.split('=')[1] || '';
}
async function api(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6500);
  try {
    const response = await fetch(path, {method:payload === undefined ? 'GET' : 'POST',
      credentials:'same-origin', cache:'no-store', signal:controller.signal,
      headers:payload === undefined ? {} : {'Content-Type':'application/json', 'X-CSRFToken':csrf()},
      body:payload === undefined ? undefined : JSON.stringify(payload)});
    let data;
    try { data = await response.json(); } catch (_) { throw new Error(`서버 응답을 확인할 수 없습니다 (${response.status}).`); }
    if (!response.ok) {
      const error = new Error(data.error || `요청 실패 (${response.status})`);
      error.data = data; throw error;
    }
    connection(true);
    return data;
  } finally { clearTimeout(timeout); }
}
function nickname() {
  const name = $('nickname').value.trim();
  if (!name || name.length > 12) throw new Error('닉네임을 1~12자로 입력하세요.');
  try { localStorage.setItem('midnight-nickname', name); } catch (_) {}
  return name;
}
// 이벤트 콜백의 실패를 한 곳에서 처리해 조용히 버튼이 먹통이 되는 것을 막습니다.
function safely(fn) { return async event => { try { await fn(event); } catch (error) { showError(error.name === 'AbortError' ? '연결이 지연되고 있습니다. 다시 시도하세요.' : error.message); } }; }
// 인원 상한은 서버 카탈로그를 사용하며, 방 생성 시 Python에서도 다시 검증합니다.
function selectedRoles() {
  return Object.fromEntries(Object.keys(roleNames).map(role => [role, Number($(`role-${role}`).value)]));
}
function setRoleDefaults() {
  if (!settingsCatalog) return;
  const defaults = settingsCatalog.by_players[$('capacity').value].defaults;
  for (const [role, count] of Object.entries(defaults)) $(`role-${role}`).value = count;
  validateRoomForm();
}
function validateRoomForm(changedRole = null) {
  if (!settingsCatalog) return false;
  const n = Number($('capacity').value), limits = settingsCatalog.by_players[n].limits;
  let roles = selectedRoles();
  // 특수직업을 조정하면 일반 시민을 남은 자리로 맞춥니다. 시민 직접 입력은 합계를 검사합니다.
  if (changedRole && changedRole !== 'citizen') {
    $('role-citizen').value = Math.max(0, n - roles.mafia - roles.police - roles.doctor);
    roles = selectedRoles();
  }
  const specialLimit = roles.mafia + settingsCatalog.special_extra;
  for (const role of Object.keys(roleNames)) {
    const available = role === 'police' ? Math.min(limits.police, specialLimit - roles.doctor)
                    : role === 'doctor' ? Math.min(limits.doctor, specialLimit - roles.police) : limits[role];
    $(`role-${role}`).max = Math.max(0, available);
  }
  $('balance-help').textContent = `마피아 최대 ${limits.mafia}명 · 경찰 최대 ${limits.police}명 · 의사 최대 ${limits.doctor}명. 경찰+의사 합계는 마피아+1명 이하입니다. 특수직업 변경 시 시민 수를 자동으로 맞춥니다.`;
  let error = '';
  for (const [role, value] of Object.entries(roles)) {
    const minimum = ['mafia','citizen'].includes(role) ? 1 : 0;
    if (!$(`role-${role}`).value || !Number.isInteger(value) || value < minimum || value > limits[role]) error = `${roleNames[role]}은 ${minimum}~${limits[role]}명으로 설정하세요.`;
  }
  if (!error && roles.police + roles.doctor > specialLimit) error = `경찰과 의사 합계를 ${specialLimit}명 이하로 줄여 주세요.`;
  const sum = Object.values(roles).reduce((a,b)=>a+b,0);
  if (!error && sum !== n) error = `역할 합계 ${sum}명 / 시작 인원 ${n}명 — 인원을 맞춰 주세요.`;
  for (const phase of ['day','vote','night']) {
    const input = $(`${phase}-seconds`), value = Number(input.value), [low,high] = settingsCatalog.time_limits[phase];
    input.min=low; input.max=high;
    if (!input.value || !Number.isInteger(value) || value<low || value>high) error = `단계별 시간 범위를 확인하세요 (${phase}: ${low}~${high}초).`;
  }
  $('settings-status').textContent = error || `역할 합계 ${sum}/${n}명 · 이 구성으로 시작합니다.`;
  $('settings-status').classList.toggle('invalid-setting', Boolean(error));
  $('create-submit').disabled = Boolean(error);
  return !error;
}
function settingsText(s) {
  const config=s.settings, times=s.durations;
  const timing=`토론 ${times.day}초 · 투표 ${times.vote}초 · 밤 ${times.night}초`;
  return config ? `${config.player_count}명 시작 · ${Object.entries(config.roles).map(([r,n])=>`${roleNames[r]} ${n}명`).join(' · ')}\n${timing}`
                : `기존 방: 4명 이상 시작 · 시작 시 인원에 맞게 역할 자동 배정\n${timing}`;
}

async function loadRooms() {
  const data = await api('/api/rooms');
  const signature = JSON.stringify(data.rooms);
  if (signature === lastLobby) return;
  lastLobby = signature;
  $('room-count').textContent = data.rooms.length;
  $('room-list').replaceChildren();
  if (!data.rooms.length) {
    const empty = node('div', 'empty');
    empty.append(node('b', '', '아직 조용한 도시'), node('span', '', '첫 번째 방을 만들고 친구들을 초대해 보세요.'));
    $('room-list').append(empty);
  }
  for (const room of data.rooms) {
    const tile = node('article', 'room-tile');
    const info = node('div');
    info.append(node('h3', '', room.title), node('p', '', `대기 중 · ${room.count}/${room.capacity}명 · ${room.code}`));
    const button = node('button', 'button secondary', room.count >= room.capacity ? '정원 마감' : '입장하기');
    button.disabled = room.count >= room.capacity;
    button.addEventListener('click', safely(() => join(room.code)));
    tile.append(info, button); $('room-list').append(tile);
  }
}
function enter(data) {
  clearError(); generation++; code = data.code; state = null;
  lastMessages = lastRoster = lastTargets = lastControls = lastReports = '';
  $('messages').replaceChildren();
  $('lobby').hidden = true; $('game').hidden = false;
  history.replaceState(null, '', `/#${code}`);
  render(data); schedulePoll(1000);
}
function toLobby() {
  generation++; code = null; state = null; clearTimeout(pollTimer);
  $('game').hidden = true; $('lobby').hidden = false;
  history.replaceState(null, '', '/'); lastLobby = '';
  loadRooms().catch(e => showError(e.message)); schedulePoll(4000);
}
async function join(target) {
  const name = nickname();
  if (!/^[A-F0-9]{8}$/.test(target)) throw new Error('8자리 초대 코드를 확인하세요.');
  enter(await api(`/api/rooms/${target}/join`, {nickname:name}));
}
async function act(kind, extra = {}) {
  if (!code) return;
  const token = generation;
  try {
    const data = await api(`/api/rooms/${code}/action`, {kind, epoch:state?.epoch, ...extra});
    if (token !== generation) return;
    clearError();
    if (data.left) { toLobby(); return; }
    render(data);
  } catch (error) {
    if (token !== generation) return;
    if (error.data?.left) toLobby();
    else if (error.data?.phase) render(error.data);
    throw error;
  }
}
function render(s) {
  // 액션과 폴링의 응답 도착 순서가 뒤집혀도 옛 화면으로 돌아가지 않습니다.
  if (state && s.server_time < state.server_time) return;
  state = s; serverOffset = s.server_time * 1000 - Date.now();
  const me = s.players.find(p => p.id === s.me);
  const active = ['day','vote','night'].includes(s.phase);
  const living = s.players.filter(p => p.alive && !p.left);
  $('game-title').textContent = s.title;
  $('room-settings-summary').textContent = settingsText(s);
  $('room-code-label').textContent = `ROOM / ${s.code}`;
  $('player-count').textContent = active ? `생존 ${living.length}명` : `${s.players.filter(p => !p.left).length}/${s.capacity}명`;
  $('round-label').textContent = s.phase === 'waiting' ? '게임 대기실' : `${s.round}일차`;
  $('phase-label').textContent = phaseNames[s.phase] || s.phase;
  $('pause-banner').hidden = !s.paused;
  $('result').hidden = s.phase !== 'ended';
  $('result-title').textContent = {town:'시민팀 승리', mafia:'마피아팀 승리', cancelled:'게임 무효'}[s.winner] || '';
  $('result-text').textContent = s.reason;
  document.querySelectorAll('[data-phase]').forEach(el => el.classList.toggle('active', el.dataset.phase === s.phase));
  $('role-card').dataset.role = me.role || '';
  $('my-role').textContent = (roleNames[me.role] || '역할 배정 전') + (!me.alive && active ? ' · 사망' : '');
  $('role-description').textContent = descriptions[me.role] || (s.settings ? `설정한 ${s.settings.player_count}명이 모두 모이면 시작합니다. 준비를 눌러 주세요.` : '4명 이상 모이면 시작할 수 있습니다. 준비를 눌러 주세요.');
  $('channel-name').textContent = {public:s.phase === 'waiting' ? '대기실 채팅' : '전체 채팅', mafia:'마피아 전용 채팅', ghost:'사망자 전용 채팅'}[s.chat_channel];
  $('chat-permission').textContent = s.chat_enabled ? s.chat_channel === 'mafia' ? '동료 마피아에게만 전달' : s.chat_channel === 'ghost' ? '생존자는 볼 수 없음' : '방 참가자에게 전달' : s.paused ? '재접속 대기' : '밤에는 생존 마피아만 대화';
  $('message').disabled = $('send').disabled = !s.chat_enabled;
  $('message').placeholder = s.chat_enabled ? '메시지를 입력하세요 (최대 300자)' : '지금은 채팅할 수 없습니다';
  renderRoster(s); renderMessages(s); renderActions(s, me); renderReports(s); updateTimer();
}
function renderRoster(s) {
  const signature = JSON.stringify([s.players,s.host]);
  if (signature === lastRoster) return; lastRoster = signature;
  const fragment = document.createDocumentFragment();
  s.players.forEach((p,index) => {
    const row = node('div', `player ${p.id === s.me ? 'self' : ''} ${!p.alive ? 'dead' : ''}`);
    const info = node('div', 'player-content');
    const name = p.name + (p.id === s.me ? ' (나)' : '') + (p.id === s.host ? ' ♛' : '');
    let subtitle = p.left ? '퇴장' : !p.connected ? `접속 확인 중 · ${p.reconnect_seconds}초` : !p.alive ? '사망' : s.phase === 'waiting' ? p.id === s.host ? '방장' : p.ready ? '준비 완료' : '준비 중' : '생존';
    if (p.role) subtitle += ` · ${roleNames[p.role]}`;
    info.append(node('div','player-name', name),node('div',`player-sub ${p.ready ? 'ready-label' : ''}`,subtitle));
    row.append(node('div','avatar',String(index+1).padStart(2,'0')),info); fragment.append(row);
  }); $('roster').replaceChildren(fragment);
}
function renderMessages(s) {
  const signature = JSON.stringify(s.messages);
  if (signature === lastMessages) return; lastMessages = signature;
  const box = $('messages'), nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 90;
  const oldIds = new Set(Array.from(box.children, el => el.dataset.id));
  const incomingIds = new Set(s.messages.map(m => String(m.id)));
  // 신규 메시지만 추가해 스크린리더가 매초 전체 채팅을 읽지 않게 합니다.
  for (const el of Array.from(box.children)) if (!incomingIds.has(el.dataset.id)) el.remove();
  for (const m of s.messages) {
    if (oldIds.has(String(m.id))) continue;
    const row = node('div', `message ${m.system ? 'system' : ''} ${m.channel}`);
    row.dataset.id = m.id;
    if (!m.system) {
      const head = node('div', 'message-head');
      head.append(node('b','',m.sender),node('time','',new Date(m.time*1000).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})));
      if (m.channel !== 'public') head.append(node('span','',m.channel === 'mafia' ? '마피아' : '사망자'));
      row.append(head);
    }
    row.append(node('div','message-body',m.text)); box.append(row);
  }
  if (nearBottom || !oldIds.size) box.scrollTop = box.scrollHeight;
}
function renderActions(s, me) {
  let title='게임 준비', help='모두 준비되면 방장이 시작합니다.';
  let kind = null;
  if (s.phase === 'day') { title='대화와 추리'; help=me.alive ? '누가 수상한가요? 다음 단계에서 투표합니다.' : '사망자는 투표할 수 없습니다. 사망자 채팅으로 이야기하세요.'; }
  if (s.phase === 'vote') { title='처형 투표'; help='생존자 과반수 득표 시 처형합니다. 시간 안에 선택을 바꿀 수 있습니다.'; if(me.alive) kind='vote'; }
  if (s.phase === 'night') {
    title={mafia:'공격 대상',doctor:'보호 대상',police:'조사 대상'}[me.role] || '밤이 지나기를 기다리세요';
    help={mafia:'동료와 의견을 모으세요. 최다 선택이 동률이면 공격하지 않습니다.',doctor:'자신을 포함한 생존자 한 명을 보호하세요.',police:'마피아 여부는 밤이 끝난 후 표시됩니다.',citizen:'지금은 채팅할 수 없습니다.'}[me.role];
    if (me.alive && me.role !== 'citizen') kind='ability';
  }
  if (!me.alive && ['vote','night'].includes(s.phase)) { title='관전 중'; help='사망자는 능력·투표를 사용할 수 없습니다.'; }
  if (s.phase === 'ended') { title='다음 게임'; help='모든 역할이 공개되었습니다. 방장이 대기실로 돌아가면 다시 준비할 수 있습니다.'; }
  $('action-title').textContent=title; $('action-help').textContent=help;
  const candidates = s.players.filter(p => p.alive && !p.left && !(kind === 'ability' && ((me.role === 'mafia' && p.role === 'mafia') || (me.role === 'police' && p.id === s.me))));
  const signature=JSON.stringify([s.epoch,kind,candidates.map(p=>[p.id,p.name]),s.my_vote,s.voted,s.my_action,s.acted,s.paused,s.mafia_actions]);
  if(signature!==lastTargets) {
    lastTargets=signature; $('targets').replaceChildren();
    if(kind) {
      const selected=kind==='vote'?s.my_vote:s.my_action, submitted=kind==='vote'?s.voted:s.acted;
      for(const p of [...candidates,{id:null,name:kind==='vote'?'기권':'능력 사용 안 함'}]) {
        const button=node('button',`target ${submitted && selected===p.id?'selected':''}`);
        button.append(node('span','',p.name));
        const supporters=p.id ? Object.entries(s.mafia_actions).filter(([,v])=>v===p.id).length:0;
        button.append(node('small','',submitted && selected===p.id?'선택됨':supporters?`마피아 ${supporters}명`:''));
        button.disabled=s.paused;
        button.addEventListener('click',safely(()=>act(kind,{target:p.id})));
        $('targets').append(button);
      }
    }
  }
  const controlSig=JSON.stringify([s.phase,s.host===s.me,me.ready,s.players.filter(p=>!p.left).map(p=>[p.ready,p.connected]),s.paused]);
  if(controlSig===lastControls) return; lastControls=controlSig; $('room-controls').replaceChildren();
  function control(text,kind,extra={},disabled=false) {
    const button=node('button','button primary control-button',text); button.disabled=disabled;
    button.addEventListener('click',safely(()=>act(kind,extra))); $('room-controls').append(button);
  }
  if(s.phase==='waiting') {
    if(s.host===s.me) {
      const ps=s.players.filter(p=>!p.left);
      const needed=s.settings?.player_count || 4;
      const enough=s.settings ? ps.length===needed : ps.length>=4;
      const canStart=enough && ps.every(p=>p.connected && (p.id===s.host || p.ready));
      control(canStart?'게임 시작':!enough?`${needed}명 필요 · 현재 ${ps.length}명`:'모두의 준비를 기다리는 중','start',{},!canStart);
    } else control(me.ready?'준비 취소':'준비 완료','ready',{ready:!me.ready});
  }
  if(s.phase==='ended' && s.host===s.me) control('대기실로 돌아가기','rematch');
}
function renderReports(s) {
  $('reports-panel').hidden=!s.reports.length;
  const sig=JSON.stringify(s.reports); if(sig===lastReports)return; lastReports=sig;
  $('reports').replaceChildren(...s.reports.map(r=>node('div','report',`${r.round}일차 · ${r.name}: ${r.mafia?'마피아입니다':'마피아가 아닙니다'}`)));
}
function updateTimer() {
  if(!state)return;
  if(state.paused) { $('timer').textContent='대기'; return; }
  if(!state.deadline) { $('timer').textContent='—'; return; }
  const n=Math.max(0,Math.ceil(state.deadline-(Date.now()+serverOffset)/1000));
  $('timer').textContent=`${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;
}
function schedulePoll(delay) { clearTimeout(pollTimer); pollTimer=setTimeout(poll,delay); }
async function poll() {
  const token=generation;
  try {
    if(code) { const s=await api(`/api/rooms/${code}/sync`,{}); if(token===generation)render(s); }
    else await loadRooms();
  } catch(error) {
    if(token!==generation)return;
    if(error.data?.left) { toLobby(); showError(error.message); return; }
    connection(false); networkIssue = true;
    showError('서버 연결을 확인하고 있습니다. 유예 시간 안에 돌아오면 이어서 참여합니다.');
  } finally { if(token===generation)schedulePoll(code?1000:4000); }
}
$('create-form').addEventListener('submit',safely(async e=>{e.preventDefault(); const button=e.submitter; button.disabled=true; try{if(!validateRoomForm())throw new Error('방 설정을 확인하세요.');button.disabled=true;enter(await api('/api/rooms/create',{nickname:nickname(),title:$('room-title').value.trim(),capacity:Number($('capacity').value),day_seconds:Number($('day-seconds').value),vote_seconds:Number($('vote-seconds').value),night_seconds:Number($('night-seconds').value),role_counts:selectedRoles()}));}finally{validateRoomForm();}}));
$('capacity').addEventListener('change',setRoleDefaults);
$('reset-roles').addEventListener('click',setRoleDefaults);
for(const role of Object.keys(roleNames)) $(`role-${role}`).addEventListener('input',()=>validateRoomForm(role));
for(const phase of ['day','vote','night']) $(`${phase}-seconds`).addEventListener('input',()=>validateRoomForm());
$('join-form').addEventListener('submit',safely(async e=>{e.preventDefault();await join($('room-code').value.trim().toUpperCase());}));
$('refresh').addEventListener('click',safely(async()=>{lastLobby='';await loadRooms();clearError();}));
$('chat-form').addEventListener('submit',safely(async e=>{e.preventDefault();const text=$('message').value.trim();if(!text)return;await act('chat',{text});if($('message').value.trim()===text)$('message').value='';}));
$('leave').addEventListener('click',safely(async()=>{if(confirm('방에서 나갈까요? 게임 중이면 즉시 이탈 처리되며, 진행 조건에 따라 무효 종료될 수 있습니다.'))await act('leave');}));
$('invite').addEventListener('click',safely(async()=>{const url=`${location.origin}/#${code}`;try{await navigator.clipboard.writeText(url);$('invite').textContent='복사 완료';setTimeout(()=>$('invite').textContent='초대 링크 복사',2000);}catch(_){prompt('초대 링크를 복사해 친구에게 전달하세요.',url);}}));
$('rules-open').addEventListener('click',()=>$('rules').showModal());
$('rules-close').addEventListener('click',()=>$('rules').close());
window.addEventListener('online',()=>schedulePoll(0));
document.addEventListener('visibilitychange',()=>{if(!document.hidden)schedulePoll(0);});
setInterval(updateTimer,250);
(async()=>{
  try {
    const invite=location.hash.slice(1).toUpperCase();
    if(/^[A-F0-9]{8}$/.test(invite))$('room-code').value=invite;
    const boot=await api('/api/bootstrap');
    settingsCatalog=boot.settings_catalog; setRoleDefaults();
    if(boot.room) {
      try{enter(await api(`/api/rooms/${boot.room}/sync`,{}));return;}
      catch(e){if(!e.data?.left)throw e;}
    }
    $('lobby').hidden=false;await loadRooms();schedulePoll(4000);
  } catch(e) { $('lobby').hidden=false;connection(false);showError(`접속을 완료하지 못했습니다. 새로고침해 주세요. ${e.message}`); }
})();
