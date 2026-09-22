# `config/` — Django 프로젝트 전역 설정

> 상위 문서: [프로젝트 README](../README.md)

이 폴더는 특정 게임 기능이 아니라 **Django 프로젝트 전체가 어떻게 실행되는지**를 정하는 곳입니다. `game/`이 실제 마피아 기능을 담당한다면, `config/`는 Django에게 “어떤 앱을 쓰고, 어떤 DB에 연결하고, 어떤 URL을 어떤 View로 보낼지” 알려주는 프로젝트 설정 계층입니다.

## 파일별 역할

| 파일 | 역할 |
| --- | --- |
| `settings.py` | DB, 세션, CSRF, 정적 파일, 시간대, 보안 옵션, 환경변수 설정 |
| `urls.py` | 외부 URL을 `game.views`의 함수와 연결 |
| `wsgi.py` | Gunicorn 같은 WSGI 서버가 Django를 시작할 때 사용하는 진입점 |
| `__init__.py` | Python이 이 디렉토리를 패키지로 인식하게 함 |

## `settings.py`에서 꼭 볼 부분

### 1. 환경변수와 `.env`

비밀키나 DB 비밀번호를 코드에 직접 적지 않고 `.env`에서 읽습니다. `python scripts/init_env.py`가 `.env.example`을 바탕으로 로컬용 `.env`를 만들어 줍니다.

Django에서 이런 방식이 중요한 이유는 **코드와 실행 환경의 설정을 분리**할 수 있기 때문입니다. Git에는 코드와 예시값만 올리고, 실제 비밀번호는 서버마다 다르게 둘 수 있습니다.

### 2. MySQL과 SQLite

실제 게임은 MySQL을 사용합니다. 테스트에서는 `DJANGO_TEST_SQLITE=1`을 주면 SQLite를 사용할 수 있습니다.

다만 이 프로젝트는 `select_for_update()`를 이용해 같은 방에 대한 동시 변경을 보호하므로, **SQLite 테스트만 통과했다고 동시성까지 검증된 것은 아닙니다.** 실제 동시 입장·투표 같은 부분은 MySQL 테스트가 더 중요합니다.

### 3. 세션과 CSRF

회원가입이 없더라도 브라우저마다 Django 세션 쿠키가 만들어집니다. 이 세션을 통해 같은 사용자가 새로고침 후에도 동일한 `Guest`로 인식됩니다.

`CsrfViewMiddleware`는 브라우저에서 상태를 변경하는 POST 요청이 다른 사이트에서 위조되지 않도록 보호합니다.

### 4. 게임 서버 시간

`PRESENCE_STALE_SECONDS`, `DISCONNECT_GRACE_SECONDS`, `CLOCK_FAILURE_SECONDS`는 연결 끊김과 복귀 유예, 서버 시계 이상을 판단할 때 사용합니다. 브라우저 시간이 아니라 서버 시간이 기준입니다.

## `urls.py` 읽는 방법

예를 들어:

```python
path('api/rooms/<str:code>/action', views.room_action)
```

이라는 한 줄은 브라우저가 `/api/rooms/ABCD1234/action`로 요청하면 `game.views.room_action`이 처리한다는 뜻입니다.

전체 흐름은 다음과 같습니다.

```text
브라우저 URL
  ↓
config/urls.py
  ↓
game/views/
  ↓
game/services/
  ↓
game/domain/
```

## 새 기능을 추가할 때

예를 들어 `/api/rooms/<code>/history` API를 추가한다면 보통 다음 순서입니다.

1. `config/urls.py`에 URL 등록
2. `game/views/`에 HTTP 처리 함수 작성
3. DB 조회가 필요하면 `game/services/` 호출
4. 게임 규칙 계산이 필요하면 `game/domain/` 호출
5. `game/tests.py`에 회귀 테스트 추가

`settings.py`에는 **전역 설정만** 넣고, 개별 게임 규칙을 넣지 않는 것이 좋습니다.

## 학습 포인트

- Django의 **Project와 App 차이**
- 환경변수를 이용한 설정 분리
- URL Dispatcher
- WSGI와 Gunicorn의 관계
- 세션/CSRF 같은 미들웨어 기반 보안
