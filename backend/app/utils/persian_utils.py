from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Persian/Arabic digit maps
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
LATIN_DIGITS = "0123456789"

_FA_TO_LATIN = str.maketrans(PERSIAN_DIGITS + ARABIC_DIGITS, LATIN_DIGITS + LATIN_DIGITS)
_LATIN_TO_FA = str.maketrans(LATIN_DIGITS, PERSIAN_DIGITS)

RTL_LANGUAGES = {"fa", "ar", "he", "ur", "ku", "ps"}


def is_rtl_language(lang_code: str) -> bool:
    return lang_code.lower() in RTL_LANGUAGES


def normalize_persian_text(text: str) -> str:
    """Normalize Persian/Arabic text: fix Kaf/Yeh variants, ZWNJ, etc."""
    if not text:
        return text
    # Normalize Arabic Kaf → Persian Kaf
    text = text.replace("ك", "ک")
    # Normalize Arabic Yeh variants → Persian Yeh
    text = text.replace("ي", "ی").replace("ى", "ی")
    # Normalize Alef variants → standard Alef
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "آ")
    # Replace Arabic Hamza
    text = text.replace("ؤ", "و").replace("ئ", "ی")
    # Normalize zero-width non-joiner
    text = re.sub(r"‌+", "‌", text)
    # Remove zero-width joiner outside valid contexts
    text = text.replace("‍", "")
    # Convert Arabic-Indic digits to Western
    text = text.translate(_FA_TO_LATIN)
    # Normalize unicode
    text = unicodedata.normalize("NFC", text)
    # Collapse multiple spaces
    text = re.sub(r" +", " ", text).strip()
    return text


def to_persian_digits(text: str) -> str:
    """Convert Latin digits to Persian digits."""
    return text.translate(_LATIN_TO_FA)


def to_latin_digits(text: str) -> str:
    """Convert Persian/Arabic digits to Latin digits."""
    return text.translate(_FA_TO_LATIN)


def split_sentences_persian(text: str) -> list[str]:
    """Split Persian text into sentences for TTS chunking."""
    text = normalize_persian_text(text)
    # Split on Persian/Arabic sentence terminators and newlines
    sentences = re.split(r"[.!?؟!\n]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    # Merge very short segments with the next one
    merged: list[str] = []
    buffer = ""
    for sent in sentences:
        if len(buffer) + len(sent) < 200:
            buffer = (buffer + " " + sent).strip()
        else:
            if buffer:
                merged.append(buffer)
            buffer = sent
    if buffer:
        merged.append(buffer)
    return merged


def chunk_text_for_tts(text: str, max_chars: int = 200, language: str = "fa") -> list[str]:
    """Split text into chunks suitable for TTS synthesis."""
    if language in RTL_LANGUAGES:
        sentences = split_sentences_persian(text)
    else:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + " " + sent).strip()
        else:
            if current:
                chunks.append(current)
            if len(sent) > max_chars:
                # Split long sentence at word boundaries
                words = sent.split()
                word_chunk = ""
                for word in words:
                    if len(word_chunk) + len(word) + 1 <= max_chars:
                        word_chunk = (word_chunk + " " + word).strip()
                    else:
                        if word_chunk:
                            chunks.append(word_chunk)
                        word_chunk = word
                if word_chunk:
                    current = word_chunk
                else:
                    current = ""
            else:
                current = sent

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


def detect_language(text: str) -> str:
    """Simple heuristic language detection based on Unicode ranges."""
    if not text:
        return "en"
    persian_count = sum(1 for c in text if "؀" <= c <= "ۿ")
    total = len([c for c in text if not c.isspace()])
    if total == 0:
        return "en"
    if persian_count / total > 0.3:
        # Distinguish Persian vs Arabic by specific chars
        if any(c in text for c in "پچژگ"):
            return "fa"
        return "ar"
    return "en"


def add_rtl_mark(text: str) -> str:
    """Prepend RTL mark to text for proper display."""
    return "‏" + text


def wrap_rtl_html(text: str) -> str:
    """Wrap text in RTL HTML span."""
    return f'<span dir="rtl" lang="fa">{text}</span>'


def remove_diacritics(text: str) -> str:
    """Remove Arabic/Persian diacritics (tashkil) from text."""
    # Arabic diacritics range: U+064B to U+065F
    return re.sub(r"[ً-ٟؐ-ؚۖ-ۜ۟-ۤۧ-ۭ]", "", text)
