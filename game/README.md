# `game/` — 마피아 게임 Django 애플리케이션

> 상위 문서: [프로젝트 README](../README.md)

이 폴더가 프로젝트의 핵심입니다. Django 관점에서 `game`은 하나의 **App**이며, 데이터 모델·HTTP API·게임 규칙·프런트 화면·관리 명령을 모두 포함합니다.

이번 리팩토링에서는 한 파일에 로직을 몰아넣지 않고 다음과 같이 책임을 나눴습니다.

```text
HTTP 요청
  ↓
views/       요청 형식과 세션을 확인
  ↓
services/    ORM, transaction, select_for_update
  ↓
domain/     게임 규칙 계산
  ↓
snapshot    사용자별 공개 정보 필터링
  ↓
HTTP JSON 응답
```

## 주요 파일과 폴더

| 위치 | 책임 |
| --- | --- |
| `models.py` | `Room`, `Guest` DB 모델 |
| `views/` | HTTP 요청/응답 계층 |
| `services/` | Django ORM과 트랜잭션 계층 |
| `domain/` | Django에 최대한 의존하지 않는 순수 게임 규칙 |
| `management/commands/` | Django 사용자 정의 관리 명령 |
| `migrations/` | DB 스키마 변경 이력 |
| `static/game/` | 브라우저 JavaScript와 CSS |
| `templates/game/` | 메인 HTML 템플릿 |
| `engine.py` | 리팩토링 전 import를 유지하기 위한 호환 facade |
| `tests.py` | 규칙/API/보안/동시성 회귀 테스트 |

## `models.py`의 핵심 구조

### `Room`

방 하나를 DB 한 행으로 저장합니다. 세부 게임 상태는 `state` JSONField에 들어갑니다.

이 구조의 장점은 같은 방에 대한 변경을 `select_for_update()`로 **한 행 단위로 잠글 수 있다는 것**입니다. 두 명이 거의 동시에 투표하더라도 같은 Room 행을 순서대로 수정하게 만들 수 있습니다.

### `Guest`

회원 계정 대신 익명 참가자를 나타냅니다. UUID가 Django 세션과 연결되고, 현재 참여 중인 Room을 가리킵니다.

## 왜 `state`를 그대로 API로 보내면 안 될까?

Room의 JSON 상태에는 역할, 밤 행동, 경찰 조사 결과처럼 다른 사용자에게 보여주면 안 되는 값이 들어갈 수 있습니다.

따라서 다음처럼 해야 합니다.

```text
Room.state 원본
  ↓
domain/snapshot.py
  ↓
현재 사용자에게 허용된 정보만 JSON 응답
```

즉, 프런트엔드가 숨기는 방식이 아니라 **서버가 애초에 비밀정보를 보내지 않는 것**이 중요합니다.

## 기능을 어디에 추가해야 하나?

- 새로운 게임 규칙 → `domain/`
- DB 잠금이나 방 저장 방식 → `services/`
- 새 API → `views/`
- 화면 표시 → `static/game/app.js`, `style.css`, `templates/game/index.html`
- DB 컬럼 추가 → `models.py` + migration
- 백그라운드 처리 → `management/commands/`

## 추천 학습 순서

1. `models.py`
2. `views/README.md`
3. `services/README.md`
4. `domain/README.md`
5. `static/game/README.md`
6. `management/commands/README.md`
7. `tests.py`

처음부터 모든 게임 규칙을 읽기보다, **한 요청이 어떤 계층을 거쳐가는지** 먼저 보는 편이 이해하기 쉽습니다.
