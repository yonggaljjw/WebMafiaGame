# `game/management/commands/` — 백그라운드 게임 시계

> 상위 문서: [game/management/README.md](../README.md)

`gameclock.py`는 브라우저 요청이 없어도 서버가 게임 시간을 계속 진행할 수 있게 하는 Django 사용자 정의 명령입니다.

Docker Compose에서는 `clock` 서비스가 이 명령을 실행합니다.

```yaml
clock:
  command: ["python", "manage.py", "gameclock"]
```

## 왜 브라우저 폴링만으로 시간을 진행하지 않을까?

만약 “누군가 `/sync`를 호출할 때만 단계가 끝났는지 확인”한다면 모든 사용자가 잠시 연결을 잃었을 때 게임 시계도 멈춘 것처럼 보일 수 있습니다.

별도 `clock` 프로세스는 주기적으로 진행 중인 Room을 확인하여 서버 기준 시간을 반영합니다.

```text
clock 프로세스
  ↓ 약 1초 반복
진행 중 Room 조회
  ↓
Room 행 잠금
  ↓
domain.tick()
  ↓
필요하면 단계 변경/이탈 판정
  ↓
Room 저장
```

## 웹 서버와 clock이 동시에 Room을 수정해도 괜찮은 이유

웹 요청과 clock 모두 같은 Room을 변경할 수 있으므로 DB 행 잠금이 중요합니다. `select_for_update()`와 transaction을 통해 한쪽이 상태를 변경하는 동안 다른 쪽이 오래된 상태를 덮어쓰지 않도록 합니다.

## 학습 포인트

- Django Custom Management Command
- 웹 프로세스와 Worker 프로세스 분리
- 서버 기준 타이머
- 멀티프로세스 환경에서 DB 잠금이 필요한 이유

## 기능을 추가할 때

장시간 실행되는 서버 작업이라도 모든 것을 이 폴더에 넣을 필요는 없습니다. “주기적으로 방 상태를 점검”처럼 Django 관리 명령으로 실행할 이유가 있는 작업만 두고, 실제 게임 판정은 계속 `domain/`에 두는 것이 좋습니다.
