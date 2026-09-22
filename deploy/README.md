# `deploy/` — 외부 HTTP 진입점 설정

> 상위 문서: [프로젝트 README](../README.md)

현재 이 폴더에는 Nginx 설정인 `nginx.conf`가 있습니다.

브라우저가 Docker의 Django 컨테이너에 직접 연결하는 대신 Nginx가 앞단에서 요청을 받고 `web:8000`으로 전달합니다.

```text
브라우저 :8080
  ↓
Nginx proxy 컨테이너 :80
  ↓
Django/Gunicorn web 컨테이너 :8000
```

## `nginx.conf`에서 하는 일

### Reverse Proxy

```nginx
proxy_pass http://web:8000;
```

Docker Compose 네트워크에서 `web`이라는 서비스 이름으로 Django에 전달합니다.

### 요청 크기 제한

게임 API는 작은 JSON만 필요하므로 `client_max_body_size`를 작게 제한하여 불필요하게 큰 요청을 받지 않습니다.

### Rate Limit

IP별 요청 빈도를 제한합니다. 브라우저가 약 1초마다 폴링하므로 일반적인 게임 플레이는 허용하되 비정상적으로 많은 요청은 줄이는 목적입니다.

### 보안 Header

Content-Security-Policy, Referrer-Policy 등을 추가하여 브라우저가 외부 스크립트를 임의로 실행하거나 다른 페이지에 프레임으로 삽입되는 위험을 줄입니다.

## Nginx와 Django 역할 차이

```text
Nginx
- 외부 포트
- Reverse Proxy
- 요청 제한
- 일부 보안 Header

Django
- 세션
- CSRF
- API
- 게임 규칙
- DB 접근
```

## HTTPS를 붙일 때

현재 구성은 로컬/HTTP 테스트 중심입니다. 인터넷에 지속 운영한다면 보통 Nginx 앞이나 별도 프록시에서 TLS 인증서를 적용하고 Django의 `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, secure cookie 설정도 함께 점검해야 합니다.

## 학습 포인트

- Reverse Proxy
- Docker 서비스명 기반 내부 통신
- Rate Limiting
- HTTP Security Header
- 애플리케이션 서버와 웹 프록시 분리
