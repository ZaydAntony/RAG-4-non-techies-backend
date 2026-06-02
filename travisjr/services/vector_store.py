from uuid import uuid4
from django.conf import settings
from pinecone import Pinecone
import logging

logger = logging.getLogger(__name__)

pc = Pinecone(api_key=settings.PINECONE_APIKEY)
index = pc.Index(settings.PINECONE_INDEX)


def store_embeddings(chunks, embeddings, session_id):

    logger.info("Uploading vectors to Pinecone")

    vectors = []

    embedding_ids = []

    for chunk, embedding in zip(chunks, embeddings):

        embedding_id = str(uuid4())

        embedding_ids.append(embedding_id)

        vectors.append({
            "id": embedding_id,
            "values": embedding,
            "metadata": {
                "session_id": str(session_id),
                "text": chunk
            }
        })

    # 🚀 ONE REQUEST INSTEAD OF MANY
    index.upsert(vectors=vectors)

    logger.info(f"{len(vectors)} vectors uploaded successfully")

    return embedding_ids