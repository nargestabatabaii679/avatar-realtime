"""Unit tests for Persian text utilities."""
import pytest
from app.utils.persian_utils import (
    normalize_persian_text,
    to_persian_digits,
    to_latin_digits,
    split_sentences_persian,
    chunk_text_for_tts,
    detect_language,
    is_rtl_language,
)


def test_normalize_arabic_kaf():
    assert "ک" in normalize_persian_text("كتاب")


def test_normalize_arabic_yeh():
    assert "ی" in normalize_persian_text("يك")


def test_persian_digits():
    assert to_persian_digits("123") == "۱۲۳"
    assert to_latin_digits("۱۲۳") == "123"
    assert to_latin_digits("١٢٣") == "123"  # Arabic-Indic


def test_rtl_language_detection():
    assert is_rtl_language("fa")
    assert is_rtl_language("ar")
    assert not is_rtl_language("en")
    assert not is_rtl_language("fr")


def test_language_detection():
    assert detect_language("سلام، حالت چطور است؟") == "fa"
    assert detect_language("Hello, how are you?") == "en"


def test_sentence_splitting():
    text = "سلام. امروز هوا خوب است. من به پارک رفتم!"
    sentences = split_sentences_persian(text)
    assert len(sentences) >= 2


def test_chunk_text_for_tts():
    long_text = "این یک متن آزمایشی است. " * 20
    chunks = chunk_text_for_tts(long_text, max_chars=200, language="fa")
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 250  # allow slight overflow at word boundary
