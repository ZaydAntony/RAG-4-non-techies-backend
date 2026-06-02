import PyPDF2
from ..models import Document, Chunk
from .embeddings import embedding
from .vector_store import store_embeddings
import logging
import os

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = [".pdf"]
MAX_FILE_SIZE_MB = 5


def validate_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF files allowed")

    size_mb = os.path.getsize(file_path) / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError("File too large (max 5MB)")


def extract_text(file_path):
    logger.info("Commencing PDF File extraction")

    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    return text.strip()


def chunking(text, chunk_size=900, overlap=150):
    logger.info("Commencing Chunking")

    text = " ".join(text.split())  # normalize whitespace

    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        chunk = text[start:end].strip()

        if len(chunk) > 30:  # 🚀 filter noise chunks
            chunks.append(chunk)

        start += chunk_size - overlap

    logger.info(f"Chunking completed: {len(chunks)} chunks")
    return chunks


def ingest_document(document_id):
    document = Document.objects.select_related("session").get(id=document_id)

    logger.info(f"INGESTION STARTED FOR: {document_id}")

    try:
        document.status = "processing"
        document.save(update_fields=["status"])

        file_path = document.file.path

        validate_file(file_path)

        text = extract_text(file_path)

        if len(text) < 50:
            raise ValueError("No valid extractable text found")

        chunks = chunking(text)

        # ===============================
        # 🚀 BATCH EMBEDDING (CRITICAL SPEED BOOST)
        # ===============================
        vectors = embedding(chunks)
# 🚀 Upload ALL vectors in ONE request
        embedding_ids = store_embeddings(
            chunks=chunks,
            embeddings=vectors,
            session_id=document.session.id
        )

        chunk_objects = []

        for i, (chunk, embedding_id) in enumerate(zip(chunks, embedding_ids)):

            chunk_objects.append(
                Chunk(
                    session=document.session,
                    document=document,
                    content=chunk,
                    chunk_index=i,
                    embedding_id=embedding_id
                )
            )

        # ===============================
        # 🚀 BULK DB INSERT (BIG SPEED BOOST)
        # ===============================
        Chunk.objects.bulk_create(chunk_objects)

        document.status = "ready"
        document.save(update_fields=["status"])

        logger.info("INGESTION COMPLETED SUCCESSFULLY")

    except Exception as e:
        logger.error(f"INGESTION ERROR: {str(e)}")

        document.status = "error"
        document.save(update_fields=["status"])