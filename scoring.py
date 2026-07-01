from typing import Any


LIKELY_AI_THRESHOLD = 0.72
LIKELY_HUMAN_THRESHOLD = 0.38


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def combine_signal_scores(groq_score: float, stylometric_score: float, lexical_score: float) -> dict[str, Any]:
    combined = (groq_score * 0.45) + (stylometric_score * 0.30) + (lexical_score * 0.25)

    score_spread = max(groq_score, stylometric_score, lexical_score) - min(
        groq_score, stylometric_score, lexical_score
    )
    disagreement_dampened = False

    if score_spread > 0.35:
        combined = (combined * 0.7) + (0.5 * 0.3)
        disagreement_dampened = True

    combined = round(clamp(combined), 3)

    if combined >= LIKELY_AI_THRESHOLD:
        attribution = "likely_ai"
    elif combined <= LIKELY_HUMAN_THRESHOLD:
        attribution = "likely_human"
    else:
        attribution = "uncertain"

    return {
        "confidence": combined,
        "attribution": attribution,
        "disagreement_dampened": disagreement_dampened,
        "score_spread": round(score_spread, 3),
    }
