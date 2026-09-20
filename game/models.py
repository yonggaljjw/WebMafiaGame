"""방마다 상태를 한 행에 저장해 투표·시간 전환을 같은 잠금으로 보호합니다."""
import uuid
from django.db import models

class Room(models.Model):
    code = models.CharField(max_length=8, primary_key=True)
    title = models.CharField(max_length=40)
    capacity = models.PositiveSmallIntegerField(default=8)
    status = models.CharField(max_length=16, default='waiting', db_index=True)
    # JSON에는 비공개 역할도 있으므로 절대로 그대로 API에 반환하지 않습니다.
    state = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Guest(models.Model):
    # UUID는 세션에만 저장합니다. API에서 원하는 UUID로 로그인할 수 없습니다.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    last_create = models.FloatField(default=0)
