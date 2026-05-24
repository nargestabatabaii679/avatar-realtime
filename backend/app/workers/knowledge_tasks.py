from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from uuid import UUID

import structlog

from app.core.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="workers.knowledge_tasks.process_document_task",
    queue="cpu",
    max_retries=2,
    default_retry_delay=20,
    soft_time_limit=300,
    time_limit=420,
)
def process_document_task(
    self,
    document_id: str,
    knowledge_base_id: str,
    file_url: str,
    file_type: str,
    organization_id: str,
) -> dict:
    """Parse document, chunk, embed and store in Qdrant."""
    log = logger.bind(document_id=document_id, file_type=file_type)
    log.info("document_processing_started")

    async def _process():
        from app.core.database import AsyncSessionLocal
        from app.models.document import Document, DocumentStatus
        from app.services.storage.minio_service import download_to_path
        from app.ml.rag.document_processor import DocumentProcessor
        from app.ml.rag.embedder import Embedder
        from app.ml.rag.qdrant_store import QdrantStore
        from sqlalchemy import update

        processor = DocumentProcessor()
        embedder = Embedder()
        qdrant = QdrantStore()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ext = Path(file_url).suffix or f".{file_type}"
            source_path = tmp / f"document{ext}"

            obj_name = "/".join(file_url.split("/")[1:])
            await download_to_path("documents", obj_name, source_path)

            # Parse document into chunks
            chunks = await processor.process_file(str(source_path), file_type)
            log.info("document_parsed", chunk_count=len(chunks))

            if not chunks:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(Document)
                        .where(Document.id == UUID(document_id))
                        .values(status=DocumentStatus.FAILED, metadata={"error": "no_content_extracted"})
                    )
                    await db.commit()
                return {"status": "failed", "error": "no_content_extracted"}

            # Get or create Qdrant collection for this knowledge base
            collection_name = f"kb_{knowledge_base_id.replace('-', '')}"
            await qdrant.ensure_collection(collection_name)

            # Generate embeddings in batches of 32
            batch_size = 32
            points = []
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                texts = [c["text"] for c in batch]
                embeddings = await embedder.embed_texts(texts)
                for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                    points.append({
                        "id": f"{document_id}_{i + j}",
                        "vector": embedding,
                        "payload": {
                            "text": chunk["text"],
                            "document_id": document_id,
                            "knowledge_base_id": knowledge_base_id,
                            "page": chunk.get("page"),
                            "section": chunk.get("section"),
                            "file_type": file_type,
                        },
                    })

            await qdrant.upsert_points(collection_name, points)
            log.info("embeddings_stored", count=len(points))

            # Update document record
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Document)
                    .where(Document.id == UUID(document_id))
                    .values(
                        status=DocumentStatus.READY,
                        chunk_count=len(chunks),
                        metadata={"collection": collection_name},
                    )
                )

                from app.models.knowledge_base import KnowledgeBase
                from sqlalchemy import select
                kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == UUID(knowledge_base_id)))
                if kb:
                    kb.chunk_count = (kb.chunk_count or 0) + len(chunks)
                    kb.document_count = (kb.document_count or 0) + 1

                await db.commit()

            return {"document_id": document_id, "status": "ready", "chunks": len(chunks)}

    try:
        return asyncio.run(_process())
    except Exception as exc:
        log.error("document_processing_failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc, countdown=20)


@celery_app.task(
    name="workers.knowledge_tasks.crawl_url_task",
    queue="cpu",
    max_retries=2,
)
def crawl_url_task(
    document_id: str,
    knowledge_base_id: str,
    url: str,
    depth: int,
    organization_id: str,
) -> dict:
    """Crawl a URL and index its content into the knowledge base."""
    log = logger.bind(document_id=document_id, url=url)

    async def _crawl():
        from app.ml.rag.document_processor import DocumentProcessor
        from app.ml.rag.embedder import Embedder
        from app.ml.rag.qdrant_store import QdrantStore
        from app.core.database import AsyncSessionLocal
        from app.models.document import Document, DocumentStatus
        from sqlalchemy import update

        processor = DocumentProcessor()
        embedder = Embedder()
        qdrant = QdrantStore()

        chunks = await processor.process_url(url, depth=depth)
        if not chunks:
            return {"status": "failed", "error": "no_content"}

        collection_name = f"kb_{knowledge_base_id.replace('-', '')}"
        await qdrant.ensure_collection(collection_name)

        points = []
        texts = [c["text"] for c in chunks]
        embeddings = await embedder.embed_texts(texts)
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            points.append({
                "id": f"{document_id}_{i}",
                "vector": emb,
                "payload": {
                    "text": chunk["text"],
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "source_url": url,
                    "file_type": "url",
                },
            })

        await qdrant.upsert_points(collection_name, points)

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Document)
                .where(Document.id == UUID(document_id))
                .values(status=DocumentStatus.READY, chunk_count=len(chunks))
            )
            await db.commit()

        log.info("url_crawled", chunks=len(chunks))
        return {"document_id": document_id, "status": "ready", "chunks": len(chunks)}

    return asyncio.run(_crawl())
