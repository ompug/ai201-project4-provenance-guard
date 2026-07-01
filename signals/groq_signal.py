import json
import os
from typing import Any

from groq import Groq


MODEL_NAME = "llama-3.3-70b-versatile"


SYSTEM_PROMPT = """You are scoring whether a piece of writing appears AI-generated.
Return only valid JSON with these keys:
- ai_likelihood: number from 0 to 1
- rationale: short string explaining the strongest clue

Higher ai_likelihood means more likely AI-generated.
Be conservative about false positives. If the text could reasonably be human-written, avoid extreme scores.
"""


def analyze_text_with_groq(text: str) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "ai_likelihood": 0.5,
            "rationale": "Groq API key not configured; returned neutral placeholder score.",
            "provider": "groq",
            "model": MODEL_NAME,
            "used_fallback": True,
        }

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Score this text:\n\n{text}",
            },
        ],
    )

    raw_content = response.choices[0].message.content or "{}"
    parsed = json.loads(raw_content)

    score = float(parsed.get("ai_likelihood", 0.5))
    score = max(0.0, min(1.0, score))

    return {
        "ai_likelihood": score,
        "rationale": parsed.get("rationale", "No rationale provided."),
        "provider": "groq",
        "model": MODEL_NAME,
        "used_fallback": False,
    }
