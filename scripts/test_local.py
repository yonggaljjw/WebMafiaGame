"""Windows/Linux 모두 같은 명령으로 실행하는 SQLite 테스트 진입점입니다."""
import os
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parent.parent
if not (root / '.env').exists():
    subprocess.run([sys.executable, str(root / 'scripts/init_env.py')], check=True)
env = {**os.environ, 'DJANGO_TEST_SQLITE': '1'}
# 정적 파일도 확인하여 누락된 CSS/JS 경로를 발견합니다.
subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'], cwd=root, env=env, check=True)
subprocess.run([sys.executable, 'manage.py', 'test', 'game', '--verbosity', '1'], cwd=root, env=env, check=True)
