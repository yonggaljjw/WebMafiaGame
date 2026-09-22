# `docs/` — 프로젝트 학습·규칙·검증 문서

> 상위 문서: [프로젝트 README](../README.md)

코드만 읽으면 “왜 이렇게 만들었는지”를 놓치기 쉬워 별도의 설명 문서를 모아둔 폴더입니다.

| 문서 | 읽는 목적 |
| --- | --- |
| `LEARNING.md` | 전체 코드 학습 순서와 아키텍처 이해 |
| `RULES.md` | 실제 게임 규칙 확인 |
| `SETTINGS.md` | 방 설정 범위와 역할 밸런스 확인 |
| `VALIDATION.md` | 어떤 검증을 수행했으며 무엇이 남아 있는지 확인 |

## 추천 순서

처음 프로젝트를 공부한다면:

```text
루트 README
  ↓
docs/LEARNING.md
  ↓
game/views/README.md
  ↓
game/services/README.md
  ↓
game/domain/README.md
  ↓
docs/RULES.md
```

`RULES.md`는 “게임이 어떻게 동작해야 하는가”를 설명하고, `domain/` 코드는 그 규칙을 “어떻게 구현했는가”를 보여줍니다. 둘을 함께 비교하면 코드 읽기가 쉬워집니다.

문서를 수정할 때는 코드와 설명이 어긋나지 않도록 함께 갱신하는 것이 중요합니다.
