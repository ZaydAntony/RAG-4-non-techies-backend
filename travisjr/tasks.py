import logging
from django.conf import settings
from django.utils import timezone
from django_q.tasks import async_task
from pinecone import Pinecone
from .models import Session
from core.utils.storage import delete_pdf

logger = logging.getLogger(__name__)
pc = Pinecone(
    api_key=settings.PINECONE_APIKEY
)

index = pc.Index(
    settings.PINECONE_INDEX
)


def process_document(document_id):

    async_task(
        "travisjr.services.ingestion.ingest_document",
        document_id,
    )


def cleanup_expired_sessions():

    expired_sessions = Session.objects.filter(
        expires_at__lte=timezone.now()
    )

    total_deleted = 0

    for session in expired_sessions:

        logger.info(
            f"Cleaning session {session.id}"
        )

        try:

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
                f"Pinecone cleanup failed for session "
                f"{session.id}: {e}"
            )

        if not settings.DEBUG:

            for document in session.docs.all():

                try:

                    if document.storage_path:

                        delete_pdf(
                            document.storage_path
                        )

                        logger.info(
                            f"Deleted Supabase file "
                            f"{document.storage_path}"
                        )

                except Exception as e:

                    logger.exception(
                        f"Failed deleting Supabase file "
                        f"{document.storage_path}: {e}"
                    )

        session.delete()

        total_deleted += 1

        logger.info(
            f"Deleted expired session {session.id}"
        )

    logger.info(
        f"Cleanup complete. "
        f"Removed {total_deleted} sessions."
    )

    return total_deleted