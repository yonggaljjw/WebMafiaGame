# 한글 학습 가이드

## 1. 전체 흐름

`브라우저 → views.py → DB 잠금 → engine.py → snapshot() → 브라우저`

브라우저는 “누구에게 투표하겠다”는 의사만 전달합니다.
서버가 실제 참가자인지, 살아 있는지, 지금 투표 시간인지 검사한 후 선택을 저장합니다.
화면에서 버튼을 숨기는 것만으로는 권한 검사가 되지 않습니다.

## 2. 파일 지도

| 파일 | 공부할 내용 |
| --- | --- |
| `manage.py` | Django 명령 진입점 |
| `config/settings.py` | .env, DB, 세션, CSRF, 정적 파일 |
| `config/urls.py` | URL과 함수의 연결 |
| `game/models.py` | Room, Guest 모델 |
| `game/migrations/0001_initial.py` | 테이블 생성 이력 |
| `game/engine.py` | 웹 프레임워크와 분리한 규칙 |
| `game/views.py` | 요청 검증, 세션, 트랜잭션, 직렬화 |
| `game/management/commands/gameclock.py` | 요청이 없어도 실행하는 주기 작업 |
| `game/templates/game/index.html` | 화면 뼈대 |
| `game/static/game/app.js` | 동기화, 이벤트, 안전한 DOM 렌더링 |
| `game/static/game/style.css` | PC/모바일 레이아웃 |
| `game/tests.py` | 규칙/API/동시 입장 시나리오 |
| `docker-compose.yml` | 서비스 의존성과 환경변수 |
| `deploy/nginx.conf` | HTTP 프록시와 요청 제한 |

## 3. 방 상태를 JSON으로 저장하는 이유

소규모 방에서는 한 방의 상태를 한 번에 읽고 갱신하는 모델이 단순합니다.
`Room.state`에 참가자, 역할, 단계, 마감 시각, 투표, 밤 행동, 메시지를 묶습니다.
여러 테이블을 갱신하는 단계 전환보다 방 한 행 잠금으로 정합성을 설명하기 쉽습니다.

단점은 폴링 때 JSON을 자주 읽고 저장하며 한 방의 요청이 직렬화된다는 것입니다.
수천 개 방의 부하를 처리하는 구조로 검증한 것은 아닙니다.
규모가 커지면 참가자/메시지 테이블 분리, 이벤트 로그, WebSocket 전송 등을 검토할 수 있습니다.

| 상태 필드 | 의미 |
| --- | --- |
| settings | 확정 시작 인원, 역할별 인원, 단계별 시간 (새 방) |
| phase | waiting/day/vote/night/ended/closed |
| players | 참가자 UUID → 닉네임, 역할, 생존, 준비, 접속 시각 |
| host | 방장 UUID |
| deadline | 단계의 서버 기준 종료 시각 |
| epoch | 현재 단계만을 식별하는 무작위 값 |
| votes | 투표자 UUID → 대상 UUID 또는 null |
| actions | 밤 행동자 UUID → 대상 UUID 또는 null |
| last_tick | 마지막 서버 진행 확인 시각 |
| paused | 생존자 재접속 대기 |
| messages | 채널을 포함한 최근 200개 메시지 |

## 4. 동시 요청과 잠금

정원 4명인 방에 3명이 있을 때 두 사람이 동시에 빈자리 1개를 보고 입장하면 5명이 될 수 있습니다.
`transaction.atomic()` 안에서 `select_for_update()`로 방 행을 잠그면 첫 요청이 입장·저장을 마칠 때까지
두 번째 요청이 기다립니다. 두 번째 요청은 갱신된 4명을 보고 입장을 거부합니다.

투표와 타이머도 같은 잠금을 사용합니다. gameclock과 HTTP 요청이 동시에 마감을 발견해도
같은 밤이 두 번 처리되지 않습니다. SQLite 테스트는 MySQL의 이 잠금 동작을 보장하지 않습니다.

## 5. 익명 인증

가입하지 않아도 참가자는 식별해야 합니다. bootstrap()은 Django 세션에 무작위 Guest.id를 기록합니다.
브라우저는 HttpOnly 세션 쿠키로 식별되고 역할/투표 요청은 세션의 ID를 기준으로 처리됩니다.
JSON에 다른 UUID를 적어도 그 UUID를 자신의 신원으로 받아들이지 않습니다.

세션 테이블, Guest, Room 모두 MySQL 볼륨에 저장됩니다.
단, 서버 중단이 진행 확인 한도를 넘으면 상태를 복구하더라도 그 경기는 무효입니다.

## 6. 비밀 정보 필터링

Room.state 전체를 반환하면 개발자 도구에서 모든 직업을 볼 수 있습니다.
그래서 snapshot()이 허용할 필드만 골라 새 객체를 만듭니다.

- 내 역할만 공개하고 마피아에게는 동료 마피아도 공개
- 경찰 수사 기록은 본인에게만 공개
- 개인 투표는 본인에게만 공개
- 마피아 채팅/공격 선택은 마피아에게만 공개
- 사망자 채팅은 사망자에게만 공개
- 종료 시 전체 역할 공개

CSS로 숨기는 것이 아니라 응답에 아예 넣지 않는 방식입니다.

## 7. 타이머와 재접속

브라우저의 남은 시간은 표시용입니다. PC 시계를 바꿔도 서버 마감 시각은 바뀌지 않습니다.
epoch가 다른 예전 투표 요청이 다음날 늦게 도착하면 거절합니다.

last_seen은 정상적인 동기화/행동에서 갱신됩니다.
서버는 유예 만료를 먼저 확인하고 만료되지 않은 사람의 시각만 갱신합니다.
순서를 바꾸면 퇴장 대상이 늦은 요청 하나로 부활할 수 있습니다.

gameclock은 브라우저가 모두 닫혀도 DB를 검사합니다.
장기 지연으로 지속 가능성을 확인하지 못한 경우 무효로 처리합니다.

## 8. 프런트 코드

- api(): CSRF 헤더, JSON 요청, 6.5초 요청 제한
- enter(): 방 화면 전환
- poll(): 이전 요청이 끝난 뒤 다음 동기화 예약
- act(): 채팅/준비/투표/능력/나가기
- render(): 서버 공개 상태로 화면 갱신
- renderMessages(): 신규 메시지만 DOM에 추가
- renderActions(): 선택 가능한 대상과 본인 선택 표시

닉네임/채팅은 textContent로 넣어 HTML로 실행되지 않게 합니다.
서버 시각이 더 오래된 응답은 무시해 예전 폴링 응답이 최신 화면을 덮지 않게 합니다.

## 9. API

변경 요청은 JSON POST이며 CSRF 토큰이 필요합니다.

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | /api/bootstrap | 익명 세션 준비, 현재 방 |
| GET | /api/rooms | 공개 대기방 |
| POST | /api/rooms/create | nickname/title/capacity/day_seconds로 생성 |
| POST | /api/rooms/{code}/join | nickname으로 입장 |
| POST | /api/rooms/{code}/sync | heartbeat + 공개 상태 |
| POST | /api/rooms/{code}/action | kind에 따른 행동 |
| GET | /healthz | DB 연결 포함 웹 상태 |

kind: ready/start/chat/vote/ability/leave/rematch.
vote, ability에는 epoch와 target이 필요합니다. target: null은 기권/미사용입니다.

## 10. 관리

closed 방의 보관 기간에 따른 삭제 정책을 별도 관리 명령으로 추가할 수 있습니다.
실행 중인 방을 삭제하지 않도록 상태와 보관 기간을 함께 검사하세요.
Django 만료 세션은 `python manage.py clearsessions`로 정리할 수 있습니다.
익명 Guest와 종료된 방의 삭제 주기는 서비스 목적에 맞게 정해야 합니다.

실제 .env는 ZIP과 Git에서 제외합니다. MySQL 초기화 후 비밀번호 변경은 DB 계정과 .env를 함께 변경해야 합니다.

## 참고

- Django 트랜잭션: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
- 행 잠금: https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update
- 배포 점검: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

## 11. 방 생성 설정 확장

`balance_limits(n)`은 인원별 상한, `validate_settings()`는 역할 합계·특수직업 합계·시간 범위를 검사합니다.
`settings_catalog()` 결과를 bootstrap으로 전달하므로 프런트엔드도 서버와 같은 인원별 상한을 사용합니다.
새 방의 JSON `settings`는 DB에 저장되고 참가자의 sync 응답에도 공개됩니다. 공개되는 것은 역할별 수이며 개인별 직업은 여전히 비공개입니다.

역할 인원을 고정했는데 실제 참가자가 적으면 남는 직업을 임의로 없애지 않고 시작을 거절합니다.
start()는 저장 설정을 다시 검증하고 그 인원만큼 역할 목록을 만든 뒤 무작위로 섞습니다.
enter_phase()는 저장한 단계 시간을 마감 시각에 더합니다. rematch는 역할과 행동 기록을 초기화하되 방 설정을 유지합니다.

API 생성 필드가 추가되었습니다: `role_counts: {mafia, citizen, police, doctor}`, `vote_seconds`, `night_seconds`.
기존 `capacity`는 새 방의 시작 인원이자 정원이고 `day_seconds`는 토론 시간입니다.
role_counts를 생략하면 해당 시작 인원에 맞는 권장 구성을 사용합니다.

DB 마이그레이션은 필요 없습니다. 업데이트 전 `settings`가 없는 방은 기존 4인 이상 시작·자동 배정을 유지합니다.
