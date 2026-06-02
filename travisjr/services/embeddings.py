from django.conf import settings
import requests
import json
import logging

logger = logging.getLogger(__name__)


def embedding(chunks):
    try:
        logger.info("Initializing Embedding model")
        response = requests.post(
            url=settings.EMBEDDING_URL,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_APIKEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": "openai/text-embedding-3-small",
                "input": chunks,
                "encoding_format": "float"
            }),
            # FIX: no timeout was set — the embedding call was blocking for
            # 3+ minutes before the stream endpoint was even reached.
            # 30s is generous for a small embedding request.
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        logger.info("Chunks have been successfully embedded.")

        return [item["embedding"] for item in data["data"]]
    except Exception as e:
        logger.critical(f"Error in Embeddings File: {e}")
        raise