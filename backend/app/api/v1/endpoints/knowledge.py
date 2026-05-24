from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document, DocumentStatus, FileType
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    DocumentResponse,
    SearchRequest,
    SearchResponse,
    AddURLRequest,
    KnowledgeChatRequest,
)
from app.services.storage.minio_service import upload_file, generate_object_name

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".csv"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        name=payload.name,
        description=payload.description,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        embedding_model=payload.embedding_model or "multilingual-e5-large",
        qdrant_collection_id=f"kb_{uuid.uuid4().hex}",
        status="ready",
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.organization_id == current_user.organization_id,
            KnowledgeBase.is_deleted.is_(False),
        )
    )
    return result.scalars().all()


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)
    return kb


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)
    # Delete Qdrant collection
    try:
        from app.ml.rag.qdrant_store import QdrantStore
        qdrant = QdrantStore()
        await qdrant.delete_collection(kb.qdrant_collection_id)
    except Exception:
        pass
    kb.is_deleted = True
    await db.commit()


@router.post("/{kb_id}/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {ext} not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 100MB)")

    doc_id = uuid.uuid4()
    object_name = generate_object_name(
        str(current_user.organization_id), "documents", file.filename
    )
    await upload_file("documents", object_name, content, file.content_type or "application/octet-stream")

    file_type_map = {
        ".pdf": FileType.PDF, ".docx": FileType.DOCX, ".pptx": FileType.PPTX,
        ".xlsx": FileType.XLSX, ".txt": FileType.TXT, ".md": FileType.TXT, ".csv": FileType.TXT,
    }
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_id,
        filename=object_name,
        original_filename=file.filename,
        file_type=file_type_map.get(ext, FileType.TXT),
        file_url=f"documents/{object_name}",
        file_size_bytes=len(content),
        status=DocumentStatus.PROCESSING,
        metadata={"language": language},
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Dispatch processing task
    from app.workers.knowledge_tasks import process_document_task
    process_document_task.delay(
        document_id=str(doc_id),
        knowledge_base_id=str(kb_id),
        file_url=doc.file_url,
        file_type=ext.lstrip("."),
        organization_id=str(current_user.organization_id),
    )

    return doc


@router.post("/{kb_id}/add-url", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def add_url(
    kb_id: uuid.UUID,
    payload: AddURLRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)
    doc_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_id,
        filename=payload.url,
        original_filename=payload.url,
        file_type=FileType.URL,
        file_url=payload.url,
        file_size_bytes=0,
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    from app.workers.knowledge_tasks import crawl_url_task
    crawl_url_task.delay(
        document_id=str(doc_id),
        knowledge_base_id=str(kb_id),
        url=payload.url,
        depth=payload.depth,
        organization_id=str(current_user.organization_id),
    )
    return doc


@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_kb_or_404(db, kb_id, current_user)
    result = await db.execute(
        select(Document).where(
            Document.knowledge_base_id == kb_id,
            Document.is_deleted.is_(False),
        )
    )
    return result.scalars().all()


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)
    doc = await db.get(Document, doc_id)
    if not doc or doc.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        from app.ml.rag.qdrant_store import QdrantStore
        qdrant = QdrantStore()
        await qdrant.delete_by_document(kb.qdrant_collection_id, str(doc_id))
    except Exception:
        pass

    doc.is_deleted = True
    await db.commit()


@router.post("/{kb_id}/search", response_model=SearchResponse)
async def semantic_search(
    kb_id: uuid.UUID,
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)

    from app.ml.rag.embedder import Embedder
    from app.ml.rag.qdrant_store import QdrantStore

    embedder = Embedder()
    qdrant = QdrantStore()

    query_vec = await embedder.embed_query(payload.query)
    results = await qdrant.search(
        collection_name=kb.qdrant_collection_id,
        query_vector=query_vec,
        top_k=payload.top_k or 5,
        score_threshold=payload.score_threshold or 0.6,
        filters=payload.filters,
    )
    return {"query": payload.query, "results": results, "total": len(results)}


@router.post("/{kb_id}/chat")
async def chat_with_knowledge_base(
    kb_id: uuid.UUID,
    payload: KnowledgeChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)

    from app.ml.rag.rag_chain import RAGChain

    chain = RAGChain(
        knowledge_base_id=str(kb_id),
        language=payload.language or "fa",
        top_k=5,
    )

    if payload.stream:
        async def _gen():
            async for token in await chain.answer(payload.message, stream=True):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    response = await chain.answer(payload.message)
    return {"response": response, "kb_id": str(kb_id)}


@router.get("/{kb_id}/stats")
async def get_kb_stats(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await _get_kb_or_404(db, kb_id, current_user)

    doc_count = await db.scalar(
        select(func.count(Document.id)).where(
            Document.knowledge_base_id == kb_id, Document.is_deleted.is_(False)
        )
    )

    try:
        from app.ml.rag.qdrant_store import QdrantStore
        qdrant = QdrantStore()
        qdrant_stats = await qdrant.get_collection_stats(kb.qdrant_collection_id)
    except Exception:
        qdrant_stats = {}

    return {
        "kb_id": str(kb_id),
        "name": kb.name,
        "document_count": doc_count,
        "chunk_count": kb.chunk_count or 0,
        "vector_count": qdrant_stats.get("vector_count", 0),
        "embedding_model": kb.embedding_model,
    }


async def _get_kb_or_404(db: AsyncSession, kb_id: uuid.UUID, user: User) -> KnowledgeBase:
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb or kb.organization_id != user.organization_id or kb.is_deleted:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb
