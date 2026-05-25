"""
ml/voice/persian_tts.py
-----------------------
Persian-optimized TTS pipeline built on top of XTTSEngine.

Improvements over raw XTTS:
- Full Persian text preprocessing (numbers → words, abbreviations, diacritics)
- Phoneme-level chunking that respects Persian prosody
- Optimal synthesis parameters tuned for Persian/Farsi
- Automatic speed correction for natural Persian pacing
- Post-processing: de-essing, volume normalisation, silence trimming
"""

from __future__ import annotations

import re
import io
import time
import numpy as np
import structlog

from app.utils.persian_utils import (
    normalize_persian_text,
    chunk_text_for_tts,
    detect_language,
    remove_diacritics,
)
from app.ml.voice.xtts_engine import XTTSEngine, VoiceFingerprint, SynthesisResult, SAMPLE_RATE

logger = structlog.get_logger(__name__)

# ── Persian number-to-word tables ─────────────────────────────────────────────

_ONES = [
    "", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه",
    "ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده",
    "هفده", "هجده", "نوزده",
]
_TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
_HUNDREDS = [
    "", "صد", "دویست", "سیصد", "چهارصد", "پانصد",
    "ششصد", "هفتصد", "هشتصد", "نهصد",
]
_SCALE = ["", "هزار", "میلیون", "میلیارد", "تریلیون"]

# Common abbreviations used in Persian text
_ABBREVIATIONS: dict[str, str] = {
    "دکتر": "دکتر",
    "دکتری": "دکتری",
    "مهندس": "مهندس",
    "پروفسور": "پروفسور",
    "خ": "خیابان",
    "ک": "کوچه",
    "م": "میدان",
    "ع": "علیه‌السلام",
    "ص": "صلی‌الله‌علیه‌وآله",
    "ج": "جلد",
    "ص‌ص": "صفحات",
    "تلفن": "تلفن",
    "آقای": "آقای",
    "خانم": "خانم",
}

# Persian conjunctions / particles that should not start a TTS chunk
_NO_CHUNK_START = {"و", "یا", "که", "را", "با", "از", "به", "در", "تا", "هم"}


def _three_digit_to_words(n: int) -> str:
    """Convert 0-999 to Persian words."""
    if n == 0:
        return ""
    parts: list[str] = []
    h = n // 100
    remainder = n % 100
    if h:
        parts.append(_HUNDREDS[h])
    if remainder < 20:
        if remainder:
            parts.append(_ONES[remainder])
    else:
        t = remainder // 10
        o = remainder % 10
        parts.append(_TENS[t])
        if o:
            parts.append(_ONES[o])
    return " و ".join(parts)


def number_to_persian_words(n: int) -> str:
    """Convert an integer to Persian written form."""
    if n == 0:
        return "صفر"
    negative = n < 0
    n = abs(n)
    chunks: list[str] = []
    scale_idx = 0
    while n > 0:
        chunk = n % 1000
        if chunk:
            word = _three_digit_to_words(chunk)
            if scale_idx > 0:
                word = word + " " + _SCALE[scale_idx]
            chunks.append(word)
        n //= 1000
        scale_idx += 1
    result = " و ".join(reversed(chunks))
    return ("منفی " if negative else "") + result


def _expand_numbers(text: str) -> str:
    """Replace all Latin and Persian numerals with Persian words."""
    # Handle ordinals like ۳۵ام، 35th
    def replace_ordinal(m: re.Match) -> str:
        digits = re.sub(r"[^\d]", "", m.group(0))
        n = int(digits) if digits else 0
        return number_to_persian_words(n) + "ام"

    text = re.sub(r"[\d۰-۹]+(?:ام|مین|تم|ست)", replace_ordinal, text)

    # Handle plain numbers
    def replace_number(m: re.Match) -> str:
        digits = re.sub("[۰-۹]", lambda x: str("۰۱۲۳۴۵۶۷۸۹".index(x.group())), m.group())
        try:
            return number_to_persian_words(int(digits))
        except ValueError:
            return m.group()

    text = re.sub(r"[\d۰-۹]+", replace_number, text)
    return text


def _expand_abbreviations(text: str) -> str:
    """Expand common Persian abbreviations."""
    for abbr, expansion in _ABBREVIATIONS.items():
        text = re.sub(r"\b" + re.escape(abbr) + r"\b", expansion, text)
    return text


def _clean_punctuation_for_tts(text: str) -> str:
    """Replace punctuation that confuses TTS with pauses or nothing."""
    # Commas → slight pause marker
    text = re.sub(r"،|,", "، ", text)
    # Parentheses content → read content naturally
    text = re.sub(r"[()[\]{}]", " ", text)
    # URLs → skip
    text = re.sub(r"https?://\S+", "", text)
    # Hashtags / mentions
    text = re.sub(r"[#@]\S+", "", text)
    # Multiple dots → single pause
    text = re.sub(r"\.{2,}", ".", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess_persian_text(text: str) -> str:
    """
    Full preprocessing pipeline for Persian TTS input.

    Steps:
    1. Unicode normalisation + kaf/yeh fixes
    2. Remove diacritics
    3. Expand abbreviations
    4. Expand numbers to words
    5. Clean punctuation
    6. Final normalisation
    """
    text = normalize_persian_text(text)
    text = remove_diacritics(text)
    text = _expand_abbreviations(text)
    text = _expand_numbers(text)
    text = _clean_punctuation_for_tts(text)
    text = normalize_persian_text(text)  # second pass
    return text


def smart_chunk_persian(text: str, max_chars: int = 180) -> list[str]:
    """
    Chunk Persian text respecting prosodic boundaries.

    Prefers splitting at:
    - Sentence terminators (. ! ? ؟)
    - Comma / semicolon
    - Conjunctions at phrase boundaries
    """
    text = preprocess_persian_text(text)
    # Primary split on strong terminators
    sentences = re.split(r"(?<=[.!?؟])\s+", text)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        # Secondary split on commas if sentence is too long
        if len(sent) > max_chars:
            sub_parts = re.split(r"(?<=،)\s+", sent)
            for part in sub_parts:
                if len(current) + len(part) + 1 <= max_chars:
                    current = (current + " " + part).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = part
        else:
            if len(current) + len(sent) + 1 <= max_chars:
                current = (current + " " + sent).strip()
            else:
                if current:
                    chunks.append(current)
                current = sent
    if current:
        chunks.append(current)

    # Avoid chunks starting with particles
    result: list[str] = []
    for chunk in chunks:
        first_word = chunk.split()[0] if chunk.split() else ""
        if first_word in _NO_CHUNK_START and result:
            result[-1] = result[-1] + " " + chunk
        else:
            result.append(chunk)
    return [c.strip() for c in result if c.strip()]


# ── Audio post-processing ─────────────────────────────────────────────────────

def trim_silence(audio: np.ndarray, threshold: float = 0.01, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Trim leading and trailing silence."""
    energy = np.abs(audio)
    mask = energy > threshold
    indices = np.where(mask)[0]
    if len(indices) == 0:
        return audio
    start = max(0, indices[0] - int(0.05 * sr))   # keep 50ms lead
    end = min(len(audio), indices[-1] + int(0.1 * sr))  # keep 100ms tail
    return audio[start:end]


def add_natural_pauses(chunks_audio: list[np.ndarray], pause_ms: int = 120) -> np.ndarray:
    """Concatenate audio chunks with natural pauses between them."""
    pause = np.zeros(int(SAMPLE_RATE * pause_ms / 1000), dtype=np.float32)
    parts: list[np.ndarray] = []
    for i, chunk in enumerate(chunks_audio):
        parts.append(chunk)
        if i < len(chunks_audio) - 1:
            parts.append(pause)
    return np.concatenate(parts) if parts else np.array([], dtype=np.float32)


def apply_de_essing(audio: np.ndarray, sr: int = SAMPLE_RATE, strength: float = 0.3) -> np.ndarray:
    """
    Simple spectral de-essing to reduce harsh sibilants in Persian TTS.
    Uses a basic high-frequency energy limiter.
    """
    try:
        from scipy.signal import butter, sosfilt  # noqa: PLC0415
        # High-shelf cut above 6kHz
        sos = butter(2, 6000 / (sr / 2), btype="high", output="sos")
        high = sosfilt(sos, audio)
        energy_high = np.abs(high)
        mask = energy_high > 0.15
        audio = audio.copy()
        audio[mask] -= strength * high[mask]
        return np.clip(audio, -1.0, 1.0).astype(np.float32)
    except Exception:
        return audio


def rms_normalize(audio: np.ndarray, target_db: float = -18.0) -> np.ndarray:
    rms = np.sqrt(np.mean(audio ** 2))
    if rms < 1e-8:
        return audio
    target_rms = 10 ** (target_db / 20.0)
    return np.clip(audio * (target_rms / rms), -1.0, 1.0).astype(np.float32)


# ── Main synthesizer ──────────────────────────────────────────────────────────

class PersianTTSSynthesizer:
    """
    High-quality Persian TTS synthesizer.

    Usage::

        synth = PersianTTSSynthesizer()
        wav = synth.synthesize("سلام، حالتان چطور است؟", fingerprint)
    """

    # Tuned parameters for Persian phonology
    PERSIAN_PARAMS = dict(
        temperature=0.65,        # lower → more consistent Persian pronunciation
        top_k=40,
        top_p=0.80,
        repetition_penalty=6.0,  # higher → avoids repeated syllables
        length_penalty=1.05,     # slight length penalty for natural pacing
        speed=0.92,              # Persian sounds better slightly slower
        enable_text_splitting=False,  # we do our own splitting
    )

    def synthesize(
        self,
        text: str,
        fingerprint: VoiceFingerprint,
        speed: float = 1.0,
        language: str = "fa",
    ) -> np.ndarray:
        """
        Synthesize Persian text to audio.

        Returns:
            float32 numpy array at 24 kHz.
        """
        t0 = time.perf_counter()
        engine = XTTSEngine.get_instance()

        chunks = smart_chunk_persian(text)
        if not chunks:
            logger.warning("persian_tts_empty_text")
            return np.zeros(SAMPLE_RATE, dtype=np.float32)

        logger.info("persian_tts_start", chunks=len(chunks), text_len=len(text))

        params = {**self.PERSIAN_PARAMS, "speed": self.PERSIAN_PARAMS["speed"] * speed}

        audio_chunks: list[np.ndarray] = []
        for i, chunk in enumerate(chunks):
            result = engine.synthesize(
                text=chunk,
                fingerprint=fingerprint,
                language=language,
                **params,
            )
            if result.success and result.audio is not None:
                cleaned = trim_silence(result.audio)
                audio_chunks.append(cleaned)
            else:
                logger.warning("persian_tts_chunk_failed", chunk=i, error=result.error)

        if not audio_chunks:
            return np.zeros(SAMPLE_RATE, dtype=np.float32)

        # Concatenate with natural pauses
        final_audio = add_natural_pauses(audio_chunks, pause_ms=110)

        # Post-processing
        final_audio = apply_de_essing(final_audio)
        final_audio = rms_normalize(final_audio, target_db=-18.0)

        elapsed = (time.perf_counter() - t0) * 1000
        duration = len(final_audio) / SAMPLE_RATE
        logger.info(
            "persian_tts_done",
            duration_s=round(duration, 2),
            total_ms=round(elapsed, 1),
            rtf=round(elapsed / (duration * 1000), 3),
        )
        return final_audio

    def to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert float32 audio array to WAV bytes."""
        import soundfile as sf  # noqa: PLC0415
        buf = io.BytesIO()
        sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue()


# Singleton
_synth: PersianTTSSynthesizer | None = None


def get_persian_synthesizer() -> PersianTTSSynthesizer:
    global _synth
    if _synth is None:
        _synth = PersianTTSSynthesizer()
    return _synth
