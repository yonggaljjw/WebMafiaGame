# `scripts/` — 개발·초기화 보조 스크립트

> 상위 문서: [프로젝트 README](../README.md)

프로젝트 실행 자체의 핵심 게임 로직이 아니라, 개발자가 반복해서 수행하는 작업을 편하게 만드는 작은 Python 스크립트를 둡니다.

## `init_env.py`

`.env.example`을 읽어 실제 `.env`를 생성하고 아래 placeholder를 무작위 값으로 교체합니다.

- `REPLACE_DJANGO_SECRET` → Django `SECRET_KEY`용 URL-safe 난수
- `REPLACE_DB_PASSWORD` → 일반 MySQL 계정용 난수 비밀번호
- `REPLACE_ROOT_PASSWORD` → MySQL root 계정용 별도 난수 비밀번호

중요한 특징은 기존 `.env`가 있으면 덮어쓰지 않는다는 점입니다. 또한 `.env.example`의 placeholder 이름이 스크립트와 달라지면 그대로 파일을 생성하지 않고 오류를 내도록 검사합니다.

```bash
python scripts/init_env.py
```

환경설정 파일은 실수로 덮어쓰면 기존 DB 비밀번호나 Django 비밀키가 바뀔 수 있기 때문에 이런 보호가 필요합니다.

## `test_local.py`

로컬에서 SQLite 기반 테스트를 한 번에 실행하기 위한 편의 스크립트입니다.

대략 다음을 수행합니다.

```text
.env 확인/생성
  ↓
DJANGO_TEST_SQLITE=1
  ↓
collectstatic
  ↓
python manage.py test game
```

SQLite는 빠르고 설치가 편하지만 MySQL의 실제 행 잠금 동작과 다릅니다. 따라서 이 스크립트는 빠른 로컬 회귀 테스트용이고, 동시성까지 확인하려면 GitHub Actions의 MySQL 테스트나 Docker 환경을 사용합니다.

## 이런 스크립트를 두는 이유

README에 긴 명령을 반복해서 복사하도록 하기보다, “프로젝트에서 정한 표준 실행 절차”를 코드로 고정할 수 있습니다.

## 학습 포인트

- 개발 자동화
- 환경변수 주입
- `subprocess`로 다른 명령 실행
- 안전한 초기화 스크립트 설계
