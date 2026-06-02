from django.conf import settings
from openrouter import OpenRouter
from .retrieval import retrieve_chunks
from ..models import Chats

import logging

logger = logging.getLogger(__name__)

client = OpenRouter(
    api_key=settings.OPENROUTER_APIKEY
)

MAX_CONTEXT_CHARS = 12000
MAX_HISTORY = 10


def build_context(chunks):
    context_parts = []
    current_size = 0

    for chunk in chunks:
        chunk_text = chunk.content.strip()

        if not chunk_text:
            continue

        if current_size + len(chunk_text) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(chunk_text)
        current_size += len(chunk_text)

    return "\n\n".join(context_parts)


def generate_ai_response(query, chat_session):
    try:
        logger.info("Generating AI response")

        chunks = retrieve_chunks(
            query=query,
            session_id=chat_session.session.id
        )

        context = build_context(chunks)

        previous_chats = (
            chat_session.chats
            .all()
            .order_by("-created_at")[:MAX_HISTORY]
        )

        previous_chats = reversed(previous_chats)

        messages = [
            {
                "role": "system",
                "content": f"""
You are a helpful RAG assistant.

Answer ONLY using the provided context.

If the answer is not found in the context,
say:

"I could not find that information in the uploaded documents."

Keep responses concise and accurate.

Context:
{context}
"""
            }
        ]

        for chat in previous_chats:
            messages.append({
                "role": chat.role,
                "content": chat.chat
            })

        messages.append({
            "role": "user",
            "content": query
        })

        logger.info("Sending request to LLM")

        response = client.chat.send(
            model="openai/gpt-4.1-mini",
            messages=messages
        )

        ai_response = response.choices[0].message.content

        logger.info("LLM response received")

        Chats.objects.create(
            chatsession=chat_session,
            chat=ai_response,
            role="assistant"
        )

        return ai_response

    except Exception as e:
        logger.error(f"LLM generation failed: {str(e)}")

        Chats.objects.create(
            chatsession=chat_session,
            chat="Something went wrong while generating a response.",
            role="assistant"
        )

        return None