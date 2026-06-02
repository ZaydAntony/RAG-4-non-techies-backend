import logging
from django.utils import timezone
from .models import Session
from django.conf import settings
from django_q.tasks import async_task
from pinecone import Pinecone

pc = Pinecone(api_key=settings.PINECONE_APIKEY)
index = pc.Index(settings.PINECONE_INDEX)

logger = logging.getLogger(__name__)

def process_document(document_id):
    async_task(
        "travisjr.services.ingestion.ingest_document",
        document_id
    )

def cleanup_expired_sessions():
    expired_sessions = Session.objects.filter(
        expires_at__lte=timezone.now()
    )

    total_deleted = 0

    for session in expired_sessions:

        try:

            # Remove vectors from Pinecone

            index.delete(
                filter={
                    "session_id": str(session.id)
                }
            )

            logger.info(
                f"Pinecone vectors removed for session {session.id}"
            )

        except Exception as e:
            logger.exception(
                f"Pinecone cleanup failed for session {session.id}: {e}"
            )

        session.delete()

        total_deleted += 1

        logger.info(
            f"Deleted expired session {session.id}"
        )

    logger.info(
        f"Cleanup complete. Removed {total_deleted} sessions."
    )

    return total_deleted