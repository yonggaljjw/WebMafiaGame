"""프로젝트 최초 실행용 .env 생성 스크립트입니다.

- .env.example을 읽어 실제 .env를 만듭니다.
- Django SECRET_KEY와 MySQL 비밀번호를 안전한 난수로 생성합니다.
- 기존 .env는 절대 덮어쓰지 않습니다.
- .env.example의 placeholder가 예상과 다르면 조용히 실패하지 않고 오류를 냅니다.
"""

from pathlib import Path
import os
import secrets


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / ".env.example"
TARGET_PATH = ROOT / ".env"


# .env.example 안에서 치환할 placeholder와 실제 생성 함수를 한곳에서 관리합니다.
# Django SECRET_KEY는 URL-safe 난수를 사용하고,
# DB 비밀번호는 충분히 긴 16진수 난수를 사용합니다.
REPLACEMENTS = {
    "REPLACE_DJANGO_SECRET": lambda: secrets.token_urlsafe(50),
    "REPLACE_DB_PASSWORD": lambda: secrets.token_hex(32),
    "REPLACE_ROOT_PASSWORD": lambda: secrets.token_hex(32),
}


def build_env_text() -> str:
    """.env.example의 placeholder를 난수 값으로 바꾼 문자열을 반환합니다."""
    text = EXAMPLE_PATH.read_text(encoding="utf-8")

    for placeholder, generator in REPLACEMENTS.items():
        # 예제 파일과 스크립트의 이름이 어긋났을 때 그대로 .env가 만들어지는 일을 막습니다.
        if placeholder not in text:
            raise SystemExit(
                f"{EXAMPLE_PATH.name}에서 {placeholder!r}를 찾지 못했습니다. "
                "init_env.py와 .env.example의 placeholder를 확인하세요."
            )

        text = text.replace(placeholder, generator())

    return text


def main() -> None:
    """기존 설정을 보존하면서 최초 1회 .env를 생성합니다."""
    if TARGET_PATH.exists():
        raise SystemExit(
            ".env가 이미 있습니다. 기존 설정을 보호하기 위해 덮어쓰지 않습니다.\n"
            "새로 생성하려면 기존 .env를 직접 백업/삭제한 뒤 다시 실행하세요."
        )

    env_text = build_env_text()

    # x 모드는 파일이 이미 있으면 실패하므로 동시에 실행되어도 기존 파일을 덮어쓰지 않습니다.
    with TARGET_PATH.open("x", encoding="utf-8") as file:
        file.write(env_text)

    # Linux/macOS에서는 현재 사용자만 읽고 쓸 수 있도록 권한을 제한합니다.
    # Windows에서는 chmod 의미가 제한적이지만 실행 자체에는 문제가 없습니다.
    os.chmod(TARGET_PATH, 0o600)

    print(".env 생성 완료")
    print("- DJANGO_SECRET_KEY: 무작위 값 생성 완료")
    print("- MYSQL_PASSWORD: 무작위 값 생성 완료")
    print("- MYSQL_ROOT_PASSWORD: 무작위 값 생성 완료")
    print("이제 docker compose up -d --build 를 실행하세요.")


if __name__ == "__main__":
    main()
