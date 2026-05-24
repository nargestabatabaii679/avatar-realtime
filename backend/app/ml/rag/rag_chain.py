from __future__ import annotations

from typing import AsyncIterator, Optional
import structlog

from app.ml.rag.embedder import Embedder
from app.ml.rag.qdrant_store import QdrantStore

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI assistant with access to a knowledge base.
Answer the user's question using ONLY information from the provided context.
If the context does not contain enough information, say so clearly.
Always cite the source document when referencing specific information.
Respond in {language}. Be concise and accurate.

Context:
{context}
"""

SYSTEM_PROMPT_FA = """شما یک دستیار هوشمند هستید که به پایگاه دانش دسترسی دارید.
سوال کاربر را فقط با استفاده از اطلاعات موجود در متن زیر پاسخ دهید.
اگر متن اطلاعات کافی ندارد، صادقانه بگویید که نمی‌دانید.
منبع اطلاعات را ذکر کنید.
پاسخ را به فارسی بدهید.

متن:
{context}
"""


class RAGChain:
    """Retrieval-Augmented Generation chain for knowledge base Q&A."""

    def __init__(
        self,
        knowledge_base_id: str,
        language: str = "en",
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o-mini",
        top_k: int = 5,
        score_threshold: float = 0.6,
    ):
        self.collection_name = f"kb_{knowledge_base_id.replace('-', '')}"
        self.language = language
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.embedder = Embedder()
        self.qdrant = QdrantStore()
        self._conversation_history: list[dict] = []

    async def retrieve(self, query: str, filters: Optional[dict] = None) -> list[dict]:
        """Retrieve relevant document chunks for a query."""
        query_embedding = await self.embedder.embed_query(query)
        results = await self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            top_k=self.top_k,
            score_threshold=self.score_threshold,
            filters=filters,
        )
        return results

    async def answer(
        self,
        question: str,
        session_id: Optional[str] = None,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """Generate an answer using RAG pipeline."""
        # Retrieve context
        chunks = await self.retrieve(question)

        if not chunks:
            no_info = {
                "fa": "متأسفانه اطلاعاتی در مورد این موضوع در پایگاه دانش یافت نشد.",
                "en": "Sorry, I couldn't find relevant information in the knowledge base.",
                "ar": "عذراً، لم أجد معلومات ذات صلة في قاعدة المعرفة.",
            }
            return no_info.get(self.language, no_info["en"])

        # Build context string
        context_parts = []
        sources = []
        for i, chunk in enumerate(chunks, 1):
            doc_name = chunk["metadata"].get("document_id", "Unknown")
            context_parts.append(f"[{i}] {chunk['text']}")
            sources.append({"index": i, "document": doc_name, "score": chunk["score"]})

        context = "\n\n".join(context_parts)

        # Build prompt
        if self.language == "fa":
            system_prompt = SYSTEM_PROMPT_FA.format(context=context)
        else:
            lang_names = {"en": "English", "ar": "Arabic", "tr": "Turkish", "fr": "French", "de": "German"}
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                context=context,
                language=lang_names.get(self.language, "English"),
            )

        # Build messages with history (last 5 turns)
        messages = [{"role": "system", "content": system_prompt}]
        for turn in self._conversation_history[-10:]:
            messages.append(turn)
        messages.append({"role": "user", "content": question})

        # Call LLM
        from app.ml.llm.llm_router import LLMRouter
        llm = LLMRouter(provider=self.llm_provider, model=self.llm_model)

        if stream:
            return self._stream_response(llm, messages, question, sources)

        response = await llm.complete(messages)

        # Save to conversation history
        self._conversation_history.append({"role": "user", "content": question})
        self._conversation_history.append({"role": "assistant", "content": response})

        return response

    async def _stream_response(
        self, llm, messages: list[dict], question: str, sources: list[dict]
    ) -> AsyncIterator[str]:
        """Stream LLM response tokens."""
        full_response = ""
        async for token in llm.stream(messages):
            full_response += token
            yield token

        self._conversation_history.append({"role": "user", "content": question})
        self._conversation_history.append({"role": "assistant", "content": full_response})

    def clear_history(self) -> None:
        self._conversation_history.clear()
