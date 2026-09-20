# MIDNIGHT — Django 웹 마피아 게임

닉네임만으로 방을 만들고 친구들과 플레이하는 4~12인 웹 마피아 게임입니다.
마피아42의 이미지·캐릭터·상표를 복제하지 않고, 전통 마피아 규칙으로 새로 구현했습니다.

## 1. 가장 빠른 실행

Docker Engine + Compose v2 또는 Docker Desktop이 필요합니다. 아래 명령은 **이 README가 있는 프로젝트 폴더**에서 실행하세요.

```bash
# 비밀키와 DB 비밀번호가 무작위로 들어간 .env를 만듭니다. 기존 파일은 덮어쓰지 않습니다.
python scripts/init_env.py

# 이미지 빌드 → MySQL 준비 → DB 마이그레이션 → 웹/게임 시계/프록시 기동
# 첫 빌드에는 인터넷 연결과 몇 분 정도가 필요합니다.
docker compose up -d --build
```

접속: **http://localhost:8080**

Python이 PC에 설치되어 있지 않다면 첫 번째 명령 대신 다음을 실행하세요.
Windows PowerShell / Linux / macOS에서 프로젝트 폴더에 들어간 뒤 사용합니다.

```bash
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim python scripts/init_env.py
```

실행 상태와 로그:

```bash
docker compose ps
docker compose logs -f web clock
```

종료:

```bash
docker compose down
```

DB 데이터는 `mysql_data` 볼륨에 남습니다. `docker compose down -v`는 DB까지 지우므로 초기화가 목적일 때만 사용하세요.

## 2. 친구들과 접속하기

1. 닉네임을 입력하고 방 이름·시작 인원·역할별 인원·단계별 시간을 설정해 방을 만듭니다.
2. `초대 링크 복사` 또는 8자리 방 코드를 친구에게 전달합니다.
3. 친구는 **자기 기기에서 접속 가능한 서버 주소**로 들어와 닉네임을 입력하고 입장합니다.
4. 방장 외 모두 `준비 완료`를 누릅니다.
5. 설정한 시작 인원이 모두 모이면 방장이 시작할 수 있습니다. 역할 합계와 실제 시작 인원을 일치시킵니다.
6. 게임 종료 후 방장이 `대기실로 돌아가기`를 누르면 재경기를 준비합니다.

**localhost 초대 링크는 다른 PC에서 사용할 수 없습니다.** 아래 네트워크 설정을 먼저 하고,
외부에서 접속할 주소로 서버에 들어간 뒤 초대 링크를 복사하세요.

### 같은 공유기에서 접속

서버 PC의 내부 IP가 `192.168.0.10`이라면 `.env`를 다음과 같이 수정합니다.

```dotenv
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.0.10
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://192.168.0.10:8080
APP_PORT=8080
```

```bash
docker compose up -d --force-recreate
```

친구는 `http://192.168.0.10:8080`에 접속합니다. 서버 PC의 방화벽에서 TCP 8080을 허용하세요.

### 포트포워딩으로 외부 테스트

예를 들어 **외부 주소가 `203.0.113.10:18080`이고 내부 PC `192.168.0.10:8080`으로 전달**된다면:
아래 IP는 설명용이므로 실제 자신의 IP로 바꿔야 합니다.

```dotenv
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.0.10,203.0.113.10
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://192.168.0.10:8080,http://203.0.113.10:18080
APP_PORT=8080
```

- `ALLOWED_HOSTS`: 호스트/IP만 입력합니다. `http://`, 포트, 경로를 넣지 않습니다.
- `CSRF_TRUSTED_ORIGINS`: **브라우저에 입력한 정확한 프로토콜 + 호스트 + 포트**를 입력합니다.
- 외부 테스트 주소는 `http://203.0.113.10:18080`입니다.
- `.env` 수정 후 `docker compose up -d --force-recreate`로 환경변수를 다시 주입합니다.
- 프런트와 API를 같은 출처로 제공하므로 CORS 전체 허용은 필요하지 않습니다.
- DB의 3306 포트는 PC 외부로 노출하지 않습니다.

`허용되지 않은 요청입니다`라면 위 두 설정과 접속 주소를 먼저 비교하세요.
`*`로 푸는 대신 실제 접속 주소를 등록하는 방식입니다.

현재 Compose는 HTTP 테스트용입니다. 인터넷에서 지속적으로 운영하려면 도메인과 HTTPS 종료 프록시를 추가하고,
브라우저 출처를 `https://...`로 수정한 뒤 `COOKIE_SECURE=true`로 설정하세요.
현재 코드에는 전달된 `X-Forwarded-Proto`를 무조건 신뢰하는 설정을 넣지 않았으므로,
HTTPS 리디렉션은 앞단 TLS 프록시에서 처리하고 앱의 `SECURE_SSL_REDIRECT=false`를 유지할 수 있습니다.

## 3. 구현한 기능

- 익명 세션: 회원가입 없이 닉네임 입장, 동일 세션의 새로고침·재접속 지원
- 방: 생성, 대기방 목록, 초대 코드/링크, 4~12명 정원 검사, 준비 상태, 방장 승계
- 진행: 낮 토론 → 투표 → 밤, 서버 기준 타이머, 재경기
- 역할: 설정한 마피아·의사·경찰·시민 인원대로 무작위 배정, 인원별 밸런스 상한, 진영별 승리 판정
- 방 설정: 역할 수 합계 검사, 토론 30~300초·투표/밤 15~120초 설정, 참가자에게 설정 공개
- 투표: 생존자 과반수 처형, 동률/과반수 미달 시 처형 없음, 기권·선택 변경
- 밤: 마피아 전용 채팅 및 공격 합의, 의사 보호, 경찰 조사
- 사망: 능력/투표 차단, 낮 사망자 전용 채팅, 밤 채팅 제한, 종료 시 직업 공개
- 연결: 8초 접속 확인 실패 시 생존자 복귀 대기, 기본 30초 유예, 이탈 후 진행 가능 여부 판정
- 서버 장애: 진행 확인이 15초 넘게 끊기면 복구 후 무효 종료
- 권한: CSRF, 서버 측 행동 검증, 참가자별 비밀 정보 필터링, 같은 방의 DB 행 잠금
- 한국어 UI, 모바일 대응 CSS, 한글 코드 주석

새 설정의 범위·밸런스 표·업데이트 방법은 [docs/SETTINGS.md](docs/SETTINGS.md)를 확인하세요.

정확한 게임 규칙은 [docs/RULES.md](docs/RULES.md)에 정리했습니다.

## 4. 기술 구성과 처리 흐름

| 구성 | 역할 |
| --- | --- |
| Python 3.12 / Django 5.2 계열 | HTTP API, 세션, 규칙 연결, DB 트랜잭션 |
| MySQL 8.4 / InnoDB | 방 상태·익명 세션 영속 저장, 방 단위 행 잠금 |
| Vanilla JavaScript / HTML / CSS | 화면, 투표·능력 선택, 1초 주기 상태 동기화 |
| Gunicorn / WhiteNoise | Django 실행, 정적 파일 제공 |
| 별도 `gameclock` 프로세스 | 클라이언트와 독립적인 타이머·이탈 검사 |
| Nginx | 외부 HTTP 진입점, 요청 크기/빈도 제한 |
| Docker Compose | 컨테이너와 실행 순서 관리 |

실시간 전달은 **약 1초 주기의 HTTP 폴링**입니다. WebSocket 구현은 포함하지 않습니다.
소규모 친구 모임에서 설치 부담을 줄이기 위한 선택이며, 외부 유료 API·Redis·Elasticsearch는 사용하지 않습니다.
검색 엔진이 필요한 규모나 검색 기능이 없어 Elasticsearch는 넣지 않았습니다.
서버·전기·인터넷 사용 자체의 비용까지 무료로 보장하는 의미는 아닙니다.

익명 세션을 확인한 요청만 해당 방을 잠그고 상태를 변경합니다.
`game/engine.py`가 게임 규칙을 계산하고, `snapshot()`이 그 사람에게 공개할 정보만 만듭니다.
브라우저가 임의의 역할·승리·공격 결과를 전송해도 서버는 받아들이지 않습니다.

## 5. 학습 순서

1. [docs/LEARNING.md](docs/LEARNING.md)로 전체 흐름을 먼저 읽습니다.
2. `game/engine.py`: 역할·투표·밤 행동·승리 판정
3. `game/models.py`: 방 상태 JSON과 세션 참가자 관계
4. `game/views.py`: 입력 → 권한 → 트랜잭션 → 규칙 → 응답
5. `game/management/commands/gameclock.py`: 브라우저가 없어도 동작하는 게임 시계
6. `game/static/game/app.js`: 요청, 폴링, 참가자별 공개 상태 렌더링
7. `config/settings.py`, `docker-compose.yml`: 환경변수와 실행 구성
8. `game/tests.py`: 규칙·정보 노출·연결·HTTP·MySQL 동시 입장 테스트

## 6. 테스트

### Docker 없이 핵심 규칙/API 테스트

아래는 **학습/테스트 전용 SQLite 모드**입니다. SQLite는 MySQL의 행 잠금을 재현하지 않으므로 실제 다인 게임 운영에 사용하지 마세요.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-base.txt
python scripts/init_env.py
python scripts/test_local.py
```

`test_local.py`가 테스트에만 `DJANGO_TEST_SQLITE=1`을 설정합니다. 실제 `.env`의 DB 설정은 변경하지 않습니다.
MySQL 전용 동시 입장 테스트는 SQLite에서 명시적으로 건너뜁니다.

### 실제 MySQL 테스트 및 Compose 검증

`.github/workflows/tests.yml`에 MySQL 8.4 테스트와 Compose 기동 확인 작업을 포함했습니다.
저장소에 올려 GitHub Actions에서 실행할 수 있습니다. 이 파일을 제공한 시점에 해당 CI를 실행한 것은 아닙니다.

테스트 DB를 직접 사용하는 경우, 테스트 계정에는 `test_<MYSQL_DATABASE>` 데이터베이스 생성·삭제 권한이 필요합니다.
실제 사용자 데이터 DB가 아닌 별도 테스트 환경에서 `python manage.py test game`을 실행하세요.

### 수동 플레이 확인

1. 다른 브라우저·프로필·기기 4개 이상으로 같은 방에 들어갑니다.
2. 준비하고 시작해 각자 다른 역할과 숨겨진 상대 직업을 확인합니다.
3. 낮 → 투표 → 밤을 진행하며 각 역할의 선택을 확인합니다.
4. 일반 시민이 밤 채팅·밤 능력을 사용할 수 없는지 확인합니다.
5. 한 명의 네트워크를 끊고 8초 뒤 일시정지, 30초 뒤 이탈 판정을 확인합니다.
6. 유예 안에 복귀했을 때 자신의 역할과 방이 유지되는지 확인합니다.
7. 방장 퇴장, 승리 후 역할 공개, 재경기를 확인합니다.

## 7. 범위와 운영상 제한

- 소규모 익명 게임의 학습용 기본 구현입니다. 대규모 서비스의 부하·장애 복구·보안 감사를 완료한 제품은 아닙니다.
- 같은 브라우저 프로필의 여러 탭은 같은 사람입니다. 익명 가입 구조상 다중 기기로 여러 자리를 차지하는 행위를 완전히 막지 않습니다.
- 중도 관전자 입장, 비밀방 비밀번호, 랭킹, 음성 채팅, 상점, 마피아42의 특수 직업은 포함하지 않습니다.
- 브라우저가 백그라운드 탭·모바일 절전으로 폴링을 중단하면 이탈할 수 있습니다. 필요하면 `.env`의 `DISCONNECT_GRACE_SECONDS`를 15~120초 범위에서 조정하세요.
- 브라우저 새로고침으로는 연결을 유지하지만, 쿠키 삭제·다른 브라우저로의 이동은 같은 사람의 복귀로 처리하지 않습니다.
- 방당 최근 200개 메시지만 유지합니다. 메시지는 DB에 평문 저장하며, 민감한 개인정보를 채팅에 넣도록 설계하지 않았습니다.
- 닫힌 방과 오래된 익명 기록은 자동으로 삭제하지 않습니다. 보관 주기 정책은 [docs/LEARNING.md](docs/LEARNING.md)의 관리 항목을 참고하세요.
- MySQL 볼륨이 이미 존재하면 `.env`의 DB 비밀번호 변경만으로 기존 MySQL 계정 비밀번호가 바뀌지는 않습니다.
- 서버/DB 전체 장애 중에는 즉시 DB에 종료 기록을 남길 수 없습니다. 연결이 복구되면 마지막 진행 확인 시각을 검사해 무효 종료합니다.

검증 결과와 미검증 범위는 [docs/VALIDATION.md](docs/VALIDATION.md)를 확인하세요.
