"""
ml/rag/document_processor.py
-----------------------------
Multi-format document ingestion and chunking pipeline.

Supported formats:
- PDF (PyMuPDF + pytesseract OCR fallback for scanned pages)
- DOCX (python-docx)
- PPTX (python-pptx)
- XLSX (openpyxl)
- TXT / MD (direct UTF-8 reading)
- URL (newspaper3k web scraping)

Features:
- Smart chunking: semantic split → size-based split (512 tokens, 50 token overlap)
- Automatic language detection (langdetect)
- Metadata extraction: title, author, date, source
- Persian/Arabic RTL text normalisation (arabic-reshaper + python-bidi)
- Async wrappers for FastAPI event loop safety
"""

from __future__ import annotations

import asyncio
import io
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="doc_processor")

CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 50
AVG_CHARS_PER_TOKEN = 4  # rough estimate for token counting without tiktoken


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class DocumentChunk:
    text: str
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    page_number: int | None = None
    section_title: str | None = None
    language: str = "en"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return len(self.text) // AVG_CHARS_PER_TOKEN


@dataclass
class ProcessedDocument:
    chunks: list[DocumentChunk] = field(default_factory=list)
    title: str = ""
    author: str = ""
    language: str = "en"
    source: str = ""
    page_count: int = 0
    word_count: int = 0
    processing_ms: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


# ──────────────────────────────────────────────────────────────────────────────
# Document Processor
# ──────────────────────────────────────────────────────────────────────────────


class DocumentProcessor:
    """
    Unified document ingestion and chunking pipeline.

    Usage::

        processor = DocumentProcessor()
        doc = processor.process(file_path)
        # or
        doc = await DocumentProcessor.async_process(file_path)
    """

    def process(
        self,
        source: str | Path | bytes,
        source_type: str | None = None,
        source_name: str = "",
        chunk_size: int = CHUNK_SIZE_TOKENS,
        chunk_overlap: int = CHUNK_OVERLAP_TOKENS,
    ) -> ProcessedDocument:
        """
        Process a document from any supported source.

        Args:
            source: File path, URL string, or raw bytes.
            source_type: Force type ("pdf", "docx", "pptx", "xlsx", "txt", "md", "url").
            source_name: Friendly name for the document.
            chunk_size: Target chunk size in tokens.
            chunk_overlap: Overlap between consecutive chunks in tokens.

        Returns:
            ProcessedDocument with all chunks and metadata.
        """
        t0 = time.perf_counter()
        doc = ProcessedDocument(source=source_name or str(source)[:200])

        try:
            # Detect type
            if source_type is None:
                source_type = self._detect_type(source)

            # Extract raw text + metadata
            raw_text, metadata = self._extract(source, source_type)

            doc.title = metadata.get("title", source_name)
            doc.author = metadata.get("author", "")
            doc.page_count = metadata.get("page_count", 0)
            doc.metadata = metadata

            # Normalise text
            raw_text = self._normalize_text(raw_text)

            # Language detection
            doc.language = self._detect_language(raw_text[:2000])

            # Chunk
            chunks = self._chunk_text(
                raw_text,
                chunk_size=chunk_size,
                overlap=chunk_overlap,
                default_language=doc.language,
            )
            doc.chunks = chunks
            doc.word_count = len(raw_text.split())
            doc.processing_ms = (time.perf_counter() - t0) * 1000

            logger.info(
                "document_processed",
                source=doc.source,
                language=doc.language,
                chunks=len(chunks),
                words=doc.word_count,
                processing_ms=round(doc.processing_ms, 1),
            )

        except Exception as exc:
            doc.error = str(exc)
            logger.error("document_process_error", source=str(source)[:200], error=str(exc), exc_info=True)

        return doc

    # ── Async wrapper ─────────────────────────────────────────────────────────

    @classmethod
    async def async_process(
        cls,
        source: str | Path | bytes,
        source_type: str | None = None,
        source_name: str = "",
    ) -> ProcessedDocument:
        loop = asyncio.get_event_loop()
        processor = cls()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: processor.process(source, source_type, source_name),
        )

    # ── Extraction by format ──────────────────────────────────────────────────

    def _extract(self, source: Any, source_type: str) -> tuple[str, dict[str, Any]]:
        extractors = {
            "pdf": self._extract_pdf,
            "docx": self._extract_docx,
            "pptx": self._extract_pptx,
            "xlsx": self._extract_xlsx,
            "txt": self._extract_text,
            "md": self._extract_text,
            "url": self._extract_url,
        }
        extractor = extractors.get(source_type.lower())
        if extractor is None:
            raise ValueError(f"Unsupported document type: {source_type}")
        return extractor(source)

    def _extract_pdf(self, source: Any) -> tuple[str, dict[str, Any]]:
        try:
            import fitz  # PyMuPDF  # noqa: PLC0415

            if isinstance(source, bytes):
                doc = fitz.open(stream=source, filetype="pdf")
            else:
                doc = fitz.open(str(source))

            metadata: dict[str, Any] = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "page_count": doc.page_count,
            }

            text_parts: list[str] = []
            for page_num, page in enumerate(doc, start=1):
                page_text = page.get_text("text")
                if not page_text.strip():
                    # OCR fallback for scanned pages
                    page_text = self._ocr_page(page)
                text_parts.append(f"[Page {page_num}]\n{page_text}")

            doc.close()
            return "\n\n".join(text_parts), metadata

        except ImportError:
            raise ImportError("Install PyMuPDF: pip install pymupdf")

    def _ocr_page(self, page: Any) -> str:
        """OCR a PDF page image using pytesseract."""
        try:
            import pytesseract  # noqa: PLC0415
            from PIL import Image  # noqa: PLC0415

            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            return pytesseract.image_to_string(img, lang="eng+fas+ara")
        except ImportError:
            return ""
        except Exception as exc:
            logger.warning("pdf_ocr_failed", error=str(exc))
            return ""

    def _extract_docx(self, source: Any) -> tuple[str, dict[str, Any]]:
        try:
            from docx import Document  # type: ignore[import]  # noqa: PLC0415

            if isinstance(source, bytes):
                doc = Document(io.BytesIO(source))
            else:
                doc = Document(str(source))

            parts: list[str] = []
            current_heading = ""
            for para in doc.paragraphs:
                if para.style.name.startswith("Heading"):
                    current_heading = para.text
                    parts.append(f"\n## {para.text}\n")
                elif para.text.strip():
                    parts.append(para.text)

            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells)
                    parts.append(row_text)

            props = doc.core_properties
            metadata: dict[str, Any] = {
                "title": props.title or "",
                "author": props.author or "",
                "page_count": 0,
            }
            return "\n".join(parts), metadata

        except ImportError:
            raise ImportError("Install python-docx: pip install python-docx")

    def _extract_pptx(self, source: Any) -> tuple[str, dict[str, Any]]:
        try:
            from pptx import Presentation  # type: ignore[import]  # noqa: PLC0415

            if isinstance(source, bytes):
                prs = Presentation(io.BytesIO(source))
            else:
                prs = Presentation(str(source))

            parts: list[str] = []
            for slide_num, slide in enumerate(prs.slides, start=1):
                slide_texts: list[str] = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text)
                if slide_texts:
                    parts.append(f"[Slide {slide_num}]\n" + "\n".join(slide_texts))

            metadata: dict[str, Any] = {
                "title": prs.core_properties.title or "",
                "author": prs.core_properties.author or "",
                "page_count": len(prs.slides),
            }
            return "\n\n".join(parts), metadata

        except ImportError:
            raise ImportError("Install python-pptx: pip install python-pptx")

    def _extract_xlsx(self, source: Any) -> tuple[str, dict[str, Any]]:
        try:
            import openpyxl  # noqa: PLC0415

            if isinstance(source, bytes):
                wb = openpyxl.load_workbook(io.BytesIO(source), read_only=True, data_only=True)
            else:
                wb = openpyxl.load_workbook(str(source), read_only=True, data_only=True)

            parts: list[str] = []
            for sheet in wb.worksheets:
                parts.append(f"[Sheet: {sheet.title}]")
                for row in sheet.iter_rows(values_only=True):
                    row_text = " | ".join(str(c) if c is not None else "" for c in row)
                    if row_text.strip(" |"):
                        parts.append(row_text)

            metadata: dict[str, Any] = {
                "title": wb.properties.title or "",
                "author": wb.properties.creator or "",
                "page_count": len(wb.worksheets),
            }
            wb.close()
            return "\n".join(parts), metadata

        except ImportError:
            raise ImportError("Install openpyxl: pip install openpyxl")

    def _extract_text(self, source: Any) -> tuple[str, dict[str, Any]]:
        if isinstance(source, bytes):
            text = source.decode("utf-8", errors="replace")
        elif isinstance(source, (str, Path)):
            text = Path(source).read_text(encoding="utf-8", errors="replace")
        else:
            text = str(source)
        metadata: dict[str, Any] = {
            "title": Path(source).stem if isinstance(source, (str, Path)) else "",
            "author": "",
            "page_count": 0,
        }
        return text, metadata

    def _extract_url(self, source: Any) -> tuple[str, dict[str, Any]]:
        try:
            from newspaper import Article  # type: ignore[import]  # noqa: PLC0415

            url = str(source)
            article = Article(url)
            article.download()
            article.parse()
            metadata: dict[str, Any] = {
                "title": article.title or "",
                "author": ", ".join(article.authors) if article.authors else "",
                "page_count": 0,
                "publish_date": str(article.publish_date) if article.publish_date else "",
                "url": url,
            }
            return article.text, metadata

        except ImportError:
            # Fallback with httpx + BeautifulSoup
            try:
                import httpx  # noqa: PLC0415
                from bs4 import BeautifulSoup  # type: ignore[import]  # noqa: PLC0415

                resp = httpx.get(str(source), follow_redirects=True, timeout=30)
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                title_tag = soup.find("title")
                return text, {"title": title_tag.text if title_tag else "", "author": "", "page_count": 0}
            except Exception as exc:
                raise RuntimeError(f"URL extraction failed: {exc}")

    # ── Chunking ──────────────────────────────────────────────────────────────

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = CHUNK_SIZE_TOKENS,
        overlap: int = CHUNK_OVERLAP_TOKENS,
        default_language: str = "en",
    ) -> list[DocumentChunk]:
        """
        Semantic-first, size-bounded chunking.

        1. Split by paragraph boundaries (semantic).
        2. If a paragraph exceeds chunk_size, split by sentence.
        3. If still too large, hard-split by character limit.
        4. Merge short paragraphs together up to chunk_size.
        5. Add overlapping context from previous chunk.
        """
        # Sentence-aware split
        paragraphs = self._split_paragraphs(text)
        chunk_char_limit = chunk_size * AVG_CHARS_PER_TOKEN
        overlap_chars = overlap * AVG_CHARS_PER_TOKEN

        raw_chunks: list[str] = []
        current = ""

        for para in paragraphs:
            if len(para) > chunk_char_limit:
                # Split long paragraph into sentences
                sentences = self._split_sentences(para)
                for sent in sentences:
                    if len(current) + len(sent) + 1 > chunk_char_limit:
                        if current:
                            raw_chunks.append(current.strip())
                        current = sent
                    else:
                        current = (current + " " + sent).strip()
            else:
                if len(current) + len(para) + 2 > chunk_char_limit:
                    if current:
                        raw_chunks.append(current.strip())
                    current = para
                else:
                    current = (current + "\n\n" + para).strip() if current else para

        if current.strip():
            raw_chunks.append(current.strip())

        # Build DocumentChunk objects with overlap
        chunks: list[DocumentChunk] = []
        char_offset = 0

        for idx, chunk_text in enumerate(raw_chunks):
            # Prepend overlap from previous chunk
            if idx > 0 and overlap_chars > 0:
                prev = raw_chunks[idx - 1]
                overlap_text = prev[-overlap_chars:].strip()
                chunk_text = overlap_text + " " + chunk_text

            chunks.append(
                DocumentChunk(
                    text=chunk_text.strip(),
                    chunk_index=idx,
                    start_char=char_offset,
                    end_char=char_offset + len(chunk_text),
                    language=default_language,
                )
            )
            char_offset += len(raw_chunks[idx])

        return chunks

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split on double newlines or section markers."""
        parts = re.split(r"\n{2,}|\[Page \d+\]", text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Simple sentence splitter (handles Persian/Arabic end marks)."""
        sentences = re.split(r"(?<=[.!?؟۔।])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    # ── Text normalisation ────────────────────────────────────────────────────

    def _normalize_text(self, text: str) -> str:
        """Normalise whitespace and handle RTL scripts."""
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = self._normalize_arabic_persian(text)
        return text.strip()

    @staticmethod
    def _normalize_arabic_persian(text: str) -> str:
        """Normalise Arabic-script characters (Persian/Arabic)."""
        try:
            import arabic_reshaper  # noqa: PLC0415

            text = arabic_reshaper.reshape(text)
        except ImportError:
            pass

        # Common Persian normalisation
        replacements = {
            "ك": "ک",  # Arabic kaf → Persian kaf
            "ي": "ی",  # Arabic ya → Persian ya
            "‌": " ",  # ZWNJ → space (for chunking purposes)
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)

        # Normalise Arabic numerals to Persian
        arabic_to_persian = str.maketrans("٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹")
        return text.translate(arabic_to_persian)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_type(source: Any) -> str:
        if isinstance(source, str) and source.startswith(("http://", "https://")):
            return "url"
        if isinstance(source, (str, Path)):
            suffix = Path(source).suffix.lower().lstrip(".")
            return suffix if suffix else "txt"
        if isinstance(source, bytes):
            # Magic bytes detection
            if source[:4] == b"%PDF":
                return "pdf"
            if source[:4] == b"PK\x03\x04":
                return "docx"  # could be pptx/xlsx too; fallback to docx
            return "txt"
        return "txt"

    @staticmethod
    def _detect_language(text: str) -> str:
        try:
            from langdetect import detect  # noqa: PLC0415

            return detect(text)
        except Exception:
            # Heuristic: count Arabic/Persian script characters
            arabic_chars = sum(1 for c in text if "؀" <= c <= "ۿ")
            if arabic_chars / max(len(text), 1) > 0.3:
                return "fa"
            return "en"
