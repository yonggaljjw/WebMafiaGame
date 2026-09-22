# `game/views/` — HTTP 요청/응답 계층

> 상위 문서: [game/README.md](../README.md)

View는 브라우저와 Django 백엔드가 만나는 첫 번째 계층입니다. 여기서는 **HTTP에 관련된 일만 최대한 담당**하고 실제 게임 규칙과 DB 트랜잭션은 아래 계층으로 넘깁니다.

## 파일별 역할

| 파일 | 역할 |
| --- | --- |
| `common.py` | JSON 파싱, 공통 응답, 세션 Guest 생성/확인, 예외 처리, CSRF 실패 응답 |
| `pages.py` | 메인 `index.html` 렌더링 |
| `lobby.py` | 초기 bootstrap, 방 목록, 방 생성 API |
| `room.py` | 방 입장, sync, action API |
| `health.py` | 웹과 DB가 정상인지 확인하는 `/healthz` |
| `__init__.py` | `config/urls.py`에서 `game.views.xxx` 형태로 쓸 수 있게 View를 다시 export |

## View가 얇아야 하는 이유

잘못된 예시는 View 하나가 다음을 전부 하는 것입니다.

```text
JSON 파싱
+ DB 조회
+ transaction
+ 역할 판정
+ 투표 계산
+ 응답용 비밀정보 필터링
```

처음에는 편하지만 기능이 늘수록 수정하기 어려워집니다.

현재 구조는 다음처럼 나눕니다.

```text
View
 ├─ 요청 형식 확인
 ├─ 세션 사용자 확인
 ├─ Service 호출
 └─ JSON/HTTP 응답 생성

Service
 ├─ DB 잠금
 └─ Domain 호출 및 저장

Domain
 └─ 실제 게임 규칙
```

## `common.py`를 먼저 읽어야 하는 이유

여러 API가 공통으로 필요한 기능을 모아둔 곳입니다.

대표적으로:

- 요청 JSON 읽기
- 세션에 연결된 Guest 가져오기
- Domain에서 발생한 규칙 오류를 사용자용 JSON 오류로 바꾸기
- CSRF 실패 시 HTML 오류 페이지 대신 API에 맞는 응답 반환

공통 코드를 여기에 모으면 `lobby.py`, `room.py`가 더 짧아집니다.

## `sync`와 `action`의 차이

브라우저는 약 1초마다 방 상태를 동기화합니다.

- `sync`: 현재 상태를 받고 heartbeat를 갱신
- `action`: 채팅, 투표, 준비, 밤 능력 등 사용자의 명시적 행동

둘 다 같은 방 상태를 수정할 수 있으므로 실제 DB 잠금 로직은 Service에서 공통 처리합니다.

## 새 API를 추가하는 방법

예를 들어 방의 간단한 통계를 반환한다고 가정합니다.

1. `config/urls.py`에 경로 추가
2. 이 폴더에 View 함수 작성
3. 입력값을 View에서 검증
4. DB가 필요하면 Service 함수 호출
5. JSON 응답 반환
6. `game/tests.py`에 HTTP 상태코드와 응답 내용 테스트

## View에서 주의할 점

- 클라이언트 입력은 신뢰하지 않기
- 사용자 UUID나 역할을 요청 body 그대로 믿지 않기
- 상태 변경 요청은 CSRF 보호 유지
- Domain 오류 메시지를 일관된 HTTP 응답으로 변환
- DB 변경을 View에서 여기저기 직접 수행하지 않기

## 학습 포인트

- Django Function Based View
- URL Dispatcher와 View 연결
- 세션 인증과 익명 사용자 식별
- JSON API 설계
- HTTP와 Business Logic 분리
