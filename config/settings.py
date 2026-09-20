"""설정은 .env 한 곳에서 읽습니다. 실제 비밀값은 소스에 넣지 않습니다."""
import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('python scripts/init_env.py 로 .env를 먼저 생성하세요.')
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = [v.strip() for v in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if v.strip()]
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if v.strip()]
INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'game']
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request']}}]
# SQLite는 자동 테스트 전용입니다. Docker의 실제 게임은 항상 MySQL을 사용합니다.
if os.getenv('DJANGO_TEST_SQLITE') == '1':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'test.sqlite3'}}
else:
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.mysql', 'HOST': os.getenv('MYSQL_HOST', 'db'),
        'PORT': os.getenv('MYSQL_PORT', '3306'), 'NAME': os.environ['MYSQL_DATABASE'],
        'USER': os.environ['MYSQL_USER'], 'PASSWORD': os.environ['MYSQL_PASSWORD'],
        'CONN_MAX_AGE': 60, 'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                    'isolation_level': 'read committed'},
    }}
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
SESSION_COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'false').lower() == 'true'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 8192
CSRF_FAILURE_VIEW = 'game.views.csrf_failure'
# 서버 판정에 사용하는 시간이며, 브라우저의 시계는 신뢰하지 않습니다.
PRESENCE_STALE_SECONDS = 8
DISCONNECT_GRACE_SECONDS = int(os.getenv('DISCONNECT_GRACE_SECONDS', '30'))
if not 15 <= DISCONNECT_GRACE_SECONDS <= 120:
    raise ImproperlyConfigured('DISCONNECT_GRACE_SECONDS는 15~120초여야 합니다.')
CLOCK_FAILURE_SECONDS = 15
