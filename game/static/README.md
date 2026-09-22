# `game/static/` — 정적 파일 영역

> 상위 문서: [game/README.md](../README.md)

Django에서 CSS, JavaScript, 이미지처럼 요청할 때마다 서버가 동적으로 만들 필요가 없는 파일을 **Static File**이라고 합니다.

이 프로젝트의 실제 프런트 파일은 `static/game/` 아래에 있습니다.

```text
static/
└─ game/
   ├─ app.js
   └─ style.css
```

앱 이름인 `game/`을 한 번 더 넣는 이유는 여러 Django 앱이 각각 `style.css` 같은 같은 이름의 파일을 가져도 경로가 충돌하지 않도록 하기 위해서입니다.

운영 이미지 빌드 시 `collectstatic`이 각 앱의 정적 파일을 `STATIC_ROOT`로 모읍니다. 이 프로젝트에서는 WhiteNoise가 Django와 함께 정적 파일 제공을 돕습니다.

세부 프런트 동작은 [game/README.md](game/README.md)를 참고하세요.
