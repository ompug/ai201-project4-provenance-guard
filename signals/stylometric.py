import math
import re
from statistics import pstdev
from typing import Any


SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
WORD_RE = re.compile(r"\b[\w']+\b")


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _normalize_inverse(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.5
    normalized = 1.0 - ((value - low) / (high - low))
    return _clamp(normalized)


def analyze_stylometry(text: str) -> dict[str, Any]:
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    words = WORD_RE.findall(text.lower())

    if len(words) < 20 or len(sentences) < 2:
        return {
            "ai_likelihood": 0.5,
            "metrics": {
                "sentence_length_variance": 0.0,
                "type_token_ratio": 0.0,
                "punctuation_density": 0.0,
                "short_text_penalty": True,
            },
        }

    sentence_lengths = [len(WORD_RE.findall(sentence)) for sentence in sentences]
    sentence_length_variance = pstdev(sentence_lengths)
    unique_words = len(set(words))
    type_token_ratio = unique_words / len(words)
    punctuation_count = sum(1 for char in text if char in ",;:!?-")
    punctuation_density = punctuation_count / max(len(words), 1)

    variance_score = _normalize_inverse(sentence_length_variance, 1.5, 10.0)
    ttr_score = _normalize_inverse(type_token_ratio, 0.32, 0.68)
    punctuation_score = _normalize_inverse(punctuation_density, 0.03, 0.18)

    ai_likelihood = _clamp((variance_score * 0.45) + (ttr_score * 0.35) + (punctuation_score * 0.20))

    return {
        "ai_likelihood": round(ai_likelihood, 3),
        "metrics": {
            "sentence_length_variance": round(sentence_length_variance, 3),
            "type_token_ratio": round(type_token_ratio, 3),
            "punctuation_density": round(punctuation_density, 3),
            "short_text_penalty": False,
        },
    }
