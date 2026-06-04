from io import BytesIO
import logging

import PyPDF2
from django.conf import settings

from ..models import Document, Chunk
from .embeddings import embedding
from .vector_store import store_embeddings

from core.utils.storage import download_pdf

logger = logging.getLogger(__name__)


def extract_text(file_obj):
    logger.info("Commencing PDF extraction")

    reader = PyPDF2.PdfReader(file_obj)

    text = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text.append(page_text)

    return "\n".join(text).strip()


def chunking(text, chunk_size=900, overlap=150):
    logger.info("Commencing chunking")

    text = " ".join(text.split())

    chunks = []

    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        chunk = text[start:end].strip()

        if len(chunk) > 30:
            chunks.append(chunk)

        start += chunk_size - overlap

    logger.info(
        f"Chunking completed successfully: {len(chunks)} chunks"
    )

    return chunks


def get_document_stream(document):
    """
    Returns a readable file object.

    Development:
        Reads from local FileField.

    Production:
        Downloads from Supabase.
    """

    if settings.DEBUG:

        document.file.open("rb")

        return document.file

    pdf_bytes = download_pdf(
        document.storage_path
    )

    return BytesIO(pdf_bytes)


def ingest_document(document_id):

    document = Document.objects.select_related(
        "session"
    ).get(
        id=document_id
    )

    logger.info(
        f"INGESTION STARTED FOR: {document_id}"
    )

    try:

        document.status = "processing"
        document.save(
            update_fields=["status"]
        )

        file_stream = get_document_stream(
            document
        )

        try:

            text = extract_text(
                file_stream
            )

        finally:

            if settings.DEBUG:
                file_stream.close()

        if len(text) < 50:
            raise ValueError(
                "No valid extractable text found"
            )

        chunks = chunking(text)

        if not chunks:
            raise ValueError(
                "No valid chunks generated"
            )

        vectors = embedding(chunks)

        embedding_ids = store_embeddings(
            chunks=chunks,
            embeddings=vectors,
            session_id=document.session.id,
        )

        chunk_objects = [
            Chunk(
                session=document.session,
                document=document,
                content=chunk,
                chunk_index=index,
                embedding_id=embedding_id,
            )
            for index, (
                chunk,
                embedding_id,
            ) in enumerate(
                zip(
                    chunks,
                    embedding_ids,
                )
            )
        ]

        Chunk.objects.bulk_create(
            chunk_objects
        )

        document.status = "ready"

        document.save(
            update_fields=["status"]
        )

        logger.info(
            f"INGESTION COMPLETED FOR: {document_id}"
        )

    except Exception as e:

        logger.exception(
            f"INGESTION ERROR FOR {document_id}: {e}"
        )

        document.status = "error"

        document.save(
            update_fields=["status"]
        )