# `game/templates/game/` — 메인 HTML 화면 구조

> 상위 문서: [game/templates/README.md](../README.md)

`index.html`은 게임 화면의 **HTML 뼈대**입니다. 실제 상태 변화와 반복 렌더링은 대부분 `static/game/app.js`가 담당합니다.

## 템플릿과 JavaScript의 역할 구분

```text
index.html
- 화면 영역과 DOM id 정의
- 입력창, 버튼, 패널의 기본 구조
- CSS/JS 파일 연결

app.js
- 서버 상태를 받아 텍스트/목록 갱신
- 클릭/submit 이벤트 처리
- 방 입장, 투표, 채팅 요청
```

예를 들어 HTML에는 다음처럼 채팅 영역이 미리 존재합니다.

```html
<div id="messages" class="messages"></div>
```

그 안에 실제 메시지 말풍선을 만들어 넣는 것은 `app.js`입니다.

## Django Template을 많이 쓰지 않는 이유

이 프로젝트는 첫 페이지 이후 게임 상태를 JSON API로 계속 동기화하는 SPA에 가까운 방식입니다. 따라서 서버가 매 요청마다 HTML 전체를 다시 만드는 대신 브라우저가 DOM 일부를 갱신합니다.

## 수정할 때 주의할 점

`app.js`가 `document.getElementById(...)`로 특정 요소를 찾기 때문에 `id`를 변경하면 JavaScript도 함께 수정해야 합니다.

예:

```text
index.html의 id="messages" 변경
→ app.js에서 messages를 찾는 코드도 수정 필요
```

## 학습 포인트

- Django Template과 Static File의 관계
- HTML Semantic Element
- DOM `id`가 JavaScript와 연결되는 방식
- 서버 렌더링과 클라이언트 렌더링의 차이
