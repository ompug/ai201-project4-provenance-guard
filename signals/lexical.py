import re
from typing import Any


WORD_RE = re.compile(r"\b[\w']+\b")
FORMALITY_PHRASES = [
    "furthermore",
    "moreover",
    "additionally",
    "it is important to note",
    "in conclusion",
    "overall",
    "therefore",
    "however",
    "on the other hand",
    "in modern society",
    "stakeholders",
    "various sectors",
    "paradigm shift",
    "ethical implications",
    "responsible deployment",
]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def analyze_lexical_formality(text: str) -> dict[str, Any]:
    lowered = text.lower()
    words = WORD_RE.findall(lowered)
    if not words:
        return {
            "ai_likelihood": 0.5,
            "metrics": {"phrase_hits": 0, "formality_density": 0.0},
        }

    phrase_hits = sum(lowered.count(phrase) for phrase in FORMALITY_PHRASES)
    formality_density = phrase_hits / max(len(words), 1)
    average_word_length = sum(len(word) for word in words) / len(words)

    density_score = _clamp(formality_density / 0.04)
    length_score = _clamp((average_word_length - 4.2) / 2.3)
    ai_likelihood = _clamp((density_score * 0.75) + (length_score * 0.25))

    return {
        "ai_likelihood": round(ai_likelihood, 3),
        "metrics": {
            "phrase_hits": phrase_hits,
            "formality_density": round(formality_density, 4),
            "average_word_length": round(average_word_length, 3),
        },
    }
