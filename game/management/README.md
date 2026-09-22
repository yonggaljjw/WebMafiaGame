# `game/management/` — Django 관리 명령 확장 영역

> 상위 문서: [game/README.md](../README.md)

Django는 `python manage.py <명령>` 형식의 관리 명령을 기본 제공하며, 애플리케이션도 자신만의 명령을 추가할 수 있습니다.

이 프로젝트에서는 `management/commands/gameclock.py`를 통해 **게임 서버 시계 프로세스**를 별도로 실행합니다.

Django가 사용자 정의 명령을 찾는 폴더 규칙은 다음과 같습니다.

```text
game/
└─ management/
   └─ commands/
      └─ gameclock.py
```

즉 `gameclock.py`가 존재하면 다음 명령을 사용할 수 있습니다.

```bash
python manage.py gameclock
```

실제 학습 내용은 [commands/README.md](commands/README.md)를 먼저 읽어도 좋습니다.
