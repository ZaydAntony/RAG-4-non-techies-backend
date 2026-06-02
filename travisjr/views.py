from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
import json
from django.views.decorators.http import require_GET
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    RetrieveModelMixin,
    ListModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from datetime import timedelta

from openrouter import OpenRouter

from .models import Session, Document, Chats, ChatSession
from .serializers import (
    SessionsSerializer,
    DocumentSerializer,
    ChatsSerializer,
    ChatSessionSerializer,
)

from .tasks import process_document
from .services.retrieval import retrieve_chunks

# ============================================
# CONFIG
# ============================================

SESSION_LIFETIME = timedelta(hours=2)
MAX_MESSAGES = 10
MAX_CONTEXT_CHARS = 12000
MAX_HISTORY = 10


client = OpenRouter(api_key=settings.OPENROUTER_APIKEY)


# ============================================
# SESSION VIEW
# ============================================


class SessionViewSet(
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = SessionsSerializer

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")

    def get_queryset(self):
        return Session.objects.filter(expires_at__gte=timezone.now()).prefetch_related(
            "chat_sessions",
            "docs",
        )

    @method_decorator(ratelimit(key="ip", rate="2/h", block=True))
    def create(self, request, *args, **kwargs):

        ip = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        session = Session.objects.create(
            ip_address=ip,
            user_agent=user_agent,
            expires_at=timezone.now() + SESSION_LIFETIME,
        )

        serializer = self.get_serializer(session)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.expires_at < timezone.now():
            instance.delete()
            return Response({"error": "Session expired"}, status=410)

        return super().retrieve(request, *args, **kwargs)


# ============================================
# DOCUMENT VIEW
# ============================================


class DocumentViewSet(
    CreateModelMixin,
    RetrieveModelMixin,
    ListModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(
            session=self.kwargs["sessions_pk"]
        ).prefetch_related("chunks")

    def get_serializer_context(self):
        return {"session_id": self.kwargs["sessions_pk"]}

    def perform_create(self, serializer):
        session = get_object_or_404(Session, id=self.kwargs["sessions_pk"])

        file_obj = serializer.validated_data["file"]

        document = serializer.save(session=session, file_name=file_obj.name)

        process_document(document.id)


# ============================================
# CHAT SESSION VIEW
# ============================================


class ChatSessionViewSet(
    CreateModelMixin,
    DestroyModelMixin,
    RetrieveModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        return ChatSession.objects.filter(
            session=self.kwargs["sessions_pk"]
        ).prefetch_related("chats")

    def get_serializer_context(self):
        return {"session_id": self.kwargs["sessions_pk"]}

    def perform_create(self, serializer):
        session = get_object_or_404(Session, id=self.kwargs["sessions_pk"])

        serializer.save(session=session)


# ============================================
# CHAT VIEW
# ============================================


class ChatViewSet(
    CreateModelMixin,
    DestroyModelMixin,
    RetrieveModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    serializer_class = ChatsSerializer

    def get_queryset(self):
        return Chats.objects.filter(
            chatsession=self.kwargs["chatsessions_pk"]
        ).order_by("created_at")

    def create(self, request, *args, **kwargs):

        chat_session = get_object_or_404(ChatSession, id=self.kwargs["chatsessions_pk"])

        session = chat_session.session

        if session.message_count >= MAX_MESSAGES:
            return Response(
                {"message": "Free trial limit reached."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user_message = request.data.get("chat", "").strip()

        if not user_message:
            return Response(
                {"message": "Message cannot be empty"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Chats.objects.create(chatsession=chat_session, chat=user_message, role="user")

        session.message_count += 1
        session.save()

        return Response({"message": "Message saved"}, status=status.HTTP_201_CREATED)


# ============================================
# SSE STREAM HELPERS
# ============================================


def build_context(chunks):
    context_parts = []
    current_size = 0

    for chunk in chunks:
        text = chunk.content.strip()

        if not text:
            continue

        if current_size + len(text) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(text)
        current_size += len(text)

    return "\n\n".join(context_parts)


# ============================================
# SSE STREAM ENDPOINT
# ============================================


@require_GET
def stream_chat_response(request, chat_session_id):

    query = request.GET.get("query")

    if not query:
        return StreamingHttpResponse("Missing query", status=400)

    chat_session = ChatSession.objects.get(id=chat_session_id)

    chunks = retrieve_chunks(query=query, session_id=chat_session.session.id)

    context = build_context(chunks)

    previous_chats = list(chat_session.chats.all().order_by("-created_at")[:10])
    previous_chats = list(reversed(previous_chats))

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful RAG assistant.\n\n"
                "Answer ONLY using the provided context.\n\n"
                "If the answer is not found in the context, say: "
                "'I could not find that information in the uploaded documents.'\n\n"
                f"Context:\n{context}"
            ),
        }
    ]

    for chat in previous_chats:
        messages.append({"role": chat.role, "content": chat.chat})

    messages.append({"role": "user", "content": query})

    origin = request.META.get("HTTP_ORIGIN", "*")

    def event_stream():
        full = ""

        try:
            # FIX: use requests directly against the OpenRouter HTTP API with
            # stream=True instead of client.chat.completions.create().
            # The OpenRouter Python SDK's streaming interface differs from the
            # OpenAI SDK — .chat.completions.create() either doesn't exist or
            # returns non-iterable objects on this client, causing every chunk's
            # delta to be None and the stream to emit only the final "done" event.
            import requests as req
            import json as _json
            from django.conf import settings

            resp = req.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_APIKEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4.1-mini",
                    "messages": messages,
                    "stream": True,
                },
                stream=True,
                timeout=60,
            )

            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue

                decoded = line.decode("utf-8")

                if decoded.startswith("data: "):
                    payload = decoded[6:].strip()

                    if payload == "[DONE]":
                        break

                    try:
                        data = _json.loads(payload)
                        delta = (
                            data.get("choices", [{}])[0].get("delta", {}).get("content")
                        )

                        if delta:
                            full += delta
                            yield f"data: {_json.dumps({'token': delta})}\n\n"

                    except _json.JSONDecodeError:
                        continue

            Chats.objects.create(chatsession=chat_session, chat=full, role="assistant")

            yield f"data: {_json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {str(e)}")
            import json as _json

            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")

    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Credentials"] = "true"

    return response
