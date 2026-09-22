# `game/services/` — ORM·트랜잭션 서비스 계층

> 상위 문서: [game/README.md](../README.md)

Service 계층은 HTTP와 게임 규칙 사이에서 **DB 상태를 안전하게 읽고 저장하는 역할**을 합니다.

이 프로젝트에서는 `room_service.py`가 중심입니다.

## 계층별 책임 비교

```text
views/      "이 요청이 올바른 JSON인가? 세션 사용자는 누구인가?"
services/   "어떤 DB 행을 잠그고 언제 저장할까?"
domain/     "이 행동이 게임 규칙상 가능한가? 결과는 무엇인가?"
```

이 경계를 유지하면 View가 거대한 함수가 되는 것을 막을 수 있습니다.

## 왜 `transaction.atomic()`이 필요한가?

멀티플레이 게임에서는 거의 동시에 요청이 올 수 있습니다.

예를 들어 마지막 한 자리에 A와 B가 동시에 입장한다고 생각해보면:

```text
A: 현재 7명 확인
B: 현재 7명 확인
A: 한 명 추가 → 8명
B: 한 명 추가 → 9명  (정원 초과)
```

단순 조회 후 저장만 하면 이런 경쟁 상태(Race Condition)가 생길 수 있습니다.

`transaction.atomic()`과 `select_for_update()`를 함께 사용하면 Room 행을 잠근 상태에서 확인과 변경을 처리할 수 있습니다.

```text
A가 Room 잠금 획득
  ↓
A 입장 처리 + 저장
  ↓
A 트랜잭션 종료
  ↓
B가 최신 Room을 읽고 정원 초과를 확인
```

## `Guest → Room` 잠금 순서를 맞추는 이유

여러 요청에서 잠금 순서가 뒤섞이면 교착상태(Deadlock) 가능성이 커집니다.

예를 들어 한 코드는 Guest 후 Room, 다른 코드는 Room 후 Guest를 잠그면 서로 상대방 잠금이 풀리기를 기다릴 수 있습니다.

그래서 이 프로젝트는 가능한 한 **Guest → Room 순서**를 유지합니다.

## 주요 함수 이해하기

### `tick_room()`

현재 서버 시간을 기준으로 Domain의 `tick()`을 호출합니다. DB에는 아직 저장하지 않습니다.

### `save_room()`

JSON 상태와 검색에 사용하는 `status` 컬럼을 함께 저장합니다.

### `room_response()`

Domain의 `snapshot()`을 이용해 현재 사용자에게 공개 가능한 상태만 응답 객체로 만듭니다.

### `create_room_for_guest()`

Guest 잠금 → 기존 방 정리 → 생성 제한 확인 → Room 생성 → Guest 연결을 하나의 트랜잭션에서 처리합니다.

### `join_room_for_guest()`

동일 세션 재접속과 신규 입장을 구분하고, 방 정원 확인과 실제 추가를 같은 잠금 안에서 처리합니다.

### `update_room_for_guest()`

주기적인 `sync`와 실제 `action`의 공통 흐름입니다. Room을 잠그고 시간 진행을 반영한 다음 heartbeat 또는 행동을 처리합니다.

## Service에 넣지 말아야 할 것

- HTML 렌더링
- `request.POST` 직접 해석
- CSS/JavaScript 처리
- “마피아가 시민 수 이상이면 승리” 같은 순수 규칙

그런 코드가 생기면 각각 `views/`, 프런트엔드, `domain/`으로 이동하는 것이 좋습니다.

## 학습 포인트

- Django ORM
- `transaction.atomic()`
- `select_for_update()`
- 경쟁 상태와 행 잠금
- Application Service 패턴
- DB 저장과 Domain 계산의 분리
