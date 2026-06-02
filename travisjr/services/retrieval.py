from .embeddings import embedding
from .vector_store import index
from ..models import Chunk

import logging

logger = logging.getLogger(__name__)


def retrieve_chunks(query, session_id, top_k=5):
    logger.info("Starting chunk retrieval")

    # embedding() returns a list of vectors (one per input string).
    # For a single query we get [[...]] — unwrap to [...] for Pinecone.
    query_embedding = embedding(query)[0]

    logger.info("Querying index with top_k=5")

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter={
            "session_id": str(session_id)
        }
    )

    matches = results.get("matches", [])

    embedding_ids = [
        match["id"]
        for match in matches
    ]

    chunks = Chunk.objects.filter(
        embedding_id__in=embedding_ids
    )

    chunk_map = {
        chunk.embedding_id: chunk
        for chunk in chunks
    }

    ordered_chunks = [
        chunk_map[eid]
        for eid in embedding_ids
        if eid in chunk_map
    ]

    logger.info(f"{len(ordered_chunks)} chunks retrieved")

    return ordered_chunks