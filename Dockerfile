FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev && rm -rf /var/lib/apt/lists/*
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# 빌드용 임시 키로 정적 파일만 수집하며 실제 운영 키는 .env에서 주입됩니다.
RUN DJANGO_SECRET_KEY=build-only-not-a-secret-0000000000000000000000000000000000 DJANGO_TEST_SQLITE=1 python manage.py collectstatic --noinput
RUN useradd --uid 10001 --create-home appuser && chown -R appuser:appuser /app
USER appuser
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
