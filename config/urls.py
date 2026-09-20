from django.urls import path
from game import views
urlpatterns = [
    path('', views.index), path('api/bootstrap', views.bootstrap),
    path('api/rooms', views.rooms), path('api/rooms/create', views.create_room),
    path('api/rooms/<str:code>/join', views.join_room),
    path('api/rooms/<str:code>/sync', views.sync_room),
    path('api/rooms/<str:code>/action', views.room_action),
    path('healthz', views.health),
]
