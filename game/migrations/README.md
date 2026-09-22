# `game/migrations/` — 데이터베이스 스키마 변경 이력

> 상위 문서: [game/README.md](../README.md)

Django Migration은 `models.py`의 변경을 DB 구조에 반영하기 위한 **버전 이력**입니다.

현재 `0001_initial.py`에는 프로젝트 최초의 `Room`, `Guest` 테이블 생성 정보가 들어 있습니다.

## 기본 흐름

`models.py`를 수정한 뒤 일반적으로 다음 명령을 사용합니다.

```bash
python manage.py makemigrations
python manage.py migrate
```

- `makemigrations`: 모델 변경을 migration Python 파일로 생성
- `migrate`: 아직 적용하지 않은 migration을 실제 DB에 적용

Docker Compose에서는 `migrate` 서비스가 웹 서버보다 먼저 실행됩니다.

## Migration 파일을 함부로 지우면 안 되는 이유

이미 여러 환경에서 사용 중인 프로젝트라면 migration 파일은 단순 임시 파일이 아니라 **DB 변경 역사**입니다. 기존 파일을 지우거나 번호를 다시 만들면 다른 환경의 DB와 코드가 서로 어떤 변경까지 적용했는지 알기 어려워질 수 있습니다.

개인 학습 프로젝트에서 DB까지 완전히 초기화할 목적이 아니라면, 기존 migration을 유지하고 새 migration을 추가하는 방식이 일반적으로 안전합니다.

## 무엇을 여기서 직접 수정할까?

보통 직접 작성하지 않고 `makemigrations`가 생성하도록 합니다. 생성된 파일을 읽어보는 것은 좋은 학습이지만, 이미 적용된 migration을 나중에 임의로 바꾸는 것은 피하는 편이 좋습니다.

## 학습 포인트

- ORM Model과 실제 DB Schema의 차이
- Schema Migration
- Migration 의존성
- 애플리케이션 배포 전 migration 실행 이유
