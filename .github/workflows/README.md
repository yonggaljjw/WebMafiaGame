# `.github/workflows/` — GitHub Actions CI

> 상위 문서: [.github/README.md](../README.md)

`tests.yml`은 GitHub에 코드를 push하거나 Pull Request를 만들 때 자동으로 테스트하는 CI(Continuous Integration) 설정입니다.

## 두 종류의 검증

### 1. `mysql-tests`

실제 MySQL 8.4 서비스 컨테이너를 띄우고 Django 테스트를 실행합니다.

이 테스트가 중요한 이유는 SQLite가 `select_for_update()` 같은 MySQL의 잠금 동작을 동일하게 재현하지 못하기 때문입니다.

```text
GitHub Runner
  ├─ MySQL 8.4 서비스
  └─ Python 3.12
       ↓
     pip install
       ↓
     collectstatic
       ↓
     python manage.py test game
```

### 2. `compose-smoke`

실제 `docker compose up -d --build`가 성공하는지 확인합니다.

컨테이너가 모두 올라온 뒤:

- `/healthz` 요청 성공 여부
- 메인 페이지 응답 여부

를 확인합니다.

즉 단위 테스트만 통과하고 Docker 설정이 깨지는 문제도 잡기 위한 Smoke Test입니다.

## 실패했을 때 로그를 출력하는 이유

Compose 시작에 실패하면 `docker compose logs --no-color`를 출력하여 DB 연결 실패, migration 오류, web healthcheck 실패 같은 원인을 GitHub Actions 화면에서 바로 확인할 수 있게 합니다.

## 학습 포인트

- CI/CD 중 CI의 역할
- GitHub Actions job/service/step
- 실제 DB를 이용한 통합 테스트
- Docker Compose Smoke Test
