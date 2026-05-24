from __future__ import annotations

import asyncio
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_model = None
_model_name = "intfloat/multilingual-e5-large"


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("loading_embedding_model", model=_model_name)
        _model = SentenceTransformer(_model_name)
        logger.info("embedding_model_loaded")
    return _model


class Embedder:
    """Generates text embeddings using multilingual-e5-large (768 dims)."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or _model_name
        self.dim = 768

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        return (await self.embed_texts([text]))[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Runs in thread pool to avoid blocking."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._embed_sync, texts)
        return result

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        model = _get_model()
        # E5 models perform best with "query: " prefix for queries
        # For passages/documents, use "passage: " prefix
        formatted = [f"passage: {t}" for t in texts]
        embeddings = model.encode(
            formatted,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return embeddings.tolist()

    async def embed_query(self, query: str) -> list[float]:
        """Embed a search query (uses 'query: ' prefix for E5 models)."""
        loop = asyncio.get_event_loop()
        model = _get_model()

        def _run():
            return model.encode(
                f"query: {query}",
                normalize_embeddings=True,
            ).tolist()

        return await loop.run_in_executor(None, _run)
