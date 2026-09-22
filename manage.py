#!/usr/bin/env python
"""Django 관리 명령의 시작점: migrate, test, runserver 등을 실행합니다."""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
