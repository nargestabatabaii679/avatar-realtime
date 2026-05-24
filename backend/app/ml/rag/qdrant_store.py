from __future__ import annotations

from typing import Optional
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_client = None


def _get_client():
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        _client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    return _client


class QdrantStore:
    """Manages Qdrant vector store operations for RAG."""

    VECTOR_SIZE = 768  # multilingual-e5-large

    async def ensure_collection(self, collection_name: str) -> None:
        """Create collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams
        import asyncio

        def _create():
            client = _get_client()
            existing = [c.name for c in client.get_collections().collections]
            if collection_name not in existing:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("qdrant_collection_created", collection=collection_name)

        await asyncio.get_event_loop().run_in_executor(None, _create)

    async def upsert_points(self, collection_name: str, points: list[dict]) -> None:
        """Upsert a list of points with vectors and payloads."""
        from qdrant_client.models import PointStruct
        import asyncio

        qdrant_points = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {}))
            for p in points
        ]

        def _upsert():
            client = _get_client()
            client.upsert(collection_name=collection_name, points=qdrant_points)

        await asyncio.get_event_loop().run_in_executor(None, _upsert)
        logger.info("qdrant_upserted", collection=collection_name, count=len(points))

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float = 0.5,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Semantic search in a collection."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        import asyncio

        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        def _search():
            client = _get_client()
            results = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=qdrant_filter,
                with_payload=True,
            )
            return [
                {
                    "id": str(r.id),
                    "score": r.score,
                    "text": r.payload.get("text", ""),
                    "metadata": {k: v for k, v in r.payload.items() if k != "text"},
                }
                for r in results
            ]

        return await asyncio.get_event_loop().run_in_executor(None, _search)

    async def delete_by_document(self, collection_name: str, document_id: str) -> None:
        """Delete all points associated with a document."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        import asyncio

        def _delete():
            client = _get_client()
            client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )

        await asyncio.get_event_loop().run_in_executor(None, _delete)

    async def get_collection_stats(self, collection_name: str) -> dict:
        """Return collection info including vector count."""
        import asyncio

        def _info():
            client = _get_client()
            info = client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vector_count": info.vectors_count,
                "indexed_count": info.indexed_vectors_count,
                "status": str(info.status),
            }

        return await asyncio.get_event_loop().run_in_executor(None, _info)

    async def delete_collection(self, collection_name: str) -> None:
        """Delete an entire collection."""
        import asyncio

        def _drop():
            client = _get_client()
            client.delete_collection(collection_name)

        await asyncio.get_event_loop().run_in_executor(None, _drop)
        logger.info("qdrant_collection_deleted", collection=collection_name)
