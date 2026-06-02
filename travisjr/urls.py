from django.urls import path, include
from .views import stream_chat_response    
from rest_framework.routers import SimpleRouter
from rest_framework_nested.routers import NestedDefaultRouter
from . import views

router = SimpleRouter()
router.register("sessions", views.SessionViewSet, basename="sessions")
sessions_router = NestedDefaultRouter(router, "sessions", lookup="sessions")
sessions_router.register(
    "chatsessions", views.ChatSessionViewSet, basename="chatsessions"
)
sessions_router.register("docs", views.DocumentViewSet, basename="docs")
chatsession_router = NestedDefaultRouter(
    sessions_router, "chatsessions", lookup="chatsessions"
)
chatsession_router.register("chats", views.ChatViewSet, basename="chats")


urlpatterns = [
    path("", include(router.urls)),
    path("", include(sessions_router.urls)),
    path("", include(chatsession_router.urls)),
    path("chatsessions/<int:chat_session_id>/stream/",stream_chat_response),
]
