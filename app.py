import uuid
from datetime import UTC, datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from labels import build_transparency_label
from signals.groq_signal import analyze_text_with_groq
from signals.lexical import analyze_lexical_formality
from signals.stylometric import analyze_stylometry
from scoring import combine_signal_scores
from storage import (
    create_content,
    get_dashboard_metrics,
    get_content,
    get_recent_log_entries,
    init_db,
    is_creator_verified,
    update_content_status,
    verify_creator,
    write_audit_entry,
)


load_dotenv()


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def analyze_submission(raw_content: str, creator_id: str, content_type: str = "text", verified: bool = False) -> dict:
    content_id = str(uuid.uuid4())
    timestamp = utc_timestamp()
    groq_result = analyze_text_with_groq(raw_content)
    stylometric_result = analyze_stylometry(raw_content)
    lexical_result = analyze_lexical_formality(raw_content)
    scoring_result = combine_signal_scores(
        float(groq_result["ai_likelihood"]),
        float(stylometric_result["ai_likelihood"]),
        float(lexical_result["ai_likelihood"]),
    )

    response_body = {
        "content_id": content_id,
        "creator_id": creator_id,
        "content_type": content_type,
        "attribution": scoring_result["attribution"],
        "confidence": scoring_result["confidence"],
        "label": build_transparency_label(scoring_result["attribution"], verified=verified),
        "status": "classified",
        "verified": verified,
        "signals": {
            "groq_score": round(float(groq_result["ai_likelihood"]), 3),
            "groq_rationale": groq_result["rationale"],
            "used_fallback": groq_result["used_fallback"],
            "stylometric_score": round(float(stylometric_result["ai_likelihood"]), 3),
            "stylometric_metrics": stylometric_result["metrics"],
            "lexical_score": round(float(lexical_result["ai_likelihood"]), 3),
            "lexical_metrics": lexical_result["metrics"],
            "score_spread": scoring_result["score_spread"],
            "disagreement_dampened": scoring_result["disagreement_dampened"],
        },
        "timestamp": timestamp,
    }

    create_content(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "content_type": content_type,
            "raw_content": raw_content,
            "attribution": response_body["attribution"],
            "confidence": response_body["confidence"],
            "label": response_body["label"],
            "status": response_body["status"],
            "signal_scores": response_body["signals"],
            "created_at": timestamp,
            "verified": verified,
        }
    )

    write_audit_entry(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "event_type": "classification",
            "content_type": content_type,
            "attribution": response_body["attribution"],
            "confidence": response_body["confidence"],
            "label": response_body["label"],
            "status": response_body["status"],
            "signal_scores": response_body["signals"],
            "rationale": groq_result["rationale"],
            "timestamp": timestamp,
        }
    )

    return response_body


def metadata_to_text(payload: dict) -> str:
    content_type = payload.get("content_type")
    if content_type == "image_description":
        return (payload.get("image_description") or "").strip()
    if content_type == "structured_metadata":
        metadata = payload.get("metadata") or {}
        if isinstance(metadata, dict):
            parts = [f"{key}: {value}" for key, value in metadata.items()]
            return ". ".join(parts).strip()
    return ""


def create_app() -> Flask:
    app = Flask(__name__)
    init_db()
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],
        storage_uri="memory://",
    )

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.post("/submit")
    @limiter.limit("10 per minute; 100 per day")
    def submit() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        creator_id = (payload.get("creator_id") or "").strip()

        if not text or not creator_id:
            return {
                "error": "Both 'text' and 'creator_id' are required."
            }, 400

        verified = is_creator_verified(creator_id)
        return jsonify(analyze_submission(text, creator_id, content_type="text", verified=verified)), 200

    @app.post("/submit/metadata")
    @limiter.limit("10 per minute; 100 per day")
    def submit_metadata() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        creator_id = (payload.get("creator_id") or "").strip()
        content_type = (payload.get("content_type") or "").strip()

        if not creator_id or content_type not in {"image_description", "structured_metadata"}:
            return {
                "error": "Valid 'creator_id' and supported 'content_type' are required."
            }, 400

        derived_text = metadata_to_text(payload)
        if not derived_text:
            return {
                "error": "The selected metadata submission did not contain analyzable text."
            }, 400

        verified = is_creator_verified(creator_id)
        return jsonify(
            analyze_submission(
                derived_text,
                creator_id,
                content_type=content_type,
                verified=verified,
            )
        ), 200

    @app.post("/appeal")
    def appeal() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        content_id = (payload.get("content_id") or "").strip()
        creator_reasoning = (payload.get("creator_reasoning") or "").strip()

        if not content_id or not creator_reasoning:
            return {
                "error": "Both 'content_id' and 'creator_reasoning' are required."
            }, 400

        content = get_content(content_id)
        if content is None:
            return {"error": "Content not found."}, 404

        update_content_status(content_id, "under_review", creator_reasoning=creator_reasoning)
        timestamp = utc_timestamp()

        write_audit_entry(
            {
                "content_id": content["content_id"],
                "creator_id": content["creator_id"],
                "event_type": "appeal",
                "content_type": content["content_type"],
                "attribution": content["attribution"],
                "confidence": content["confidence"],
                "label": content["label"],
                "status": "under_review",
                "signal_scores": content["signal_scores"],
                "appeal_reasoning": creator_reasoning,
                "timestamp": timestamp,
            }
        )

        return jsonify(
            {
                "content_id": content_id,
                "status": "under_review",
                "message": "Appeal received and queued for review.",
                "creator_reasoning": creator_reasoning,
            }
        ), 200

    @app.post("/certificate/verify")
    def certificate_verify() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        creator_id = (payload.get("creator_id") or "").strip()
        verification_text = (payload.get("verification_text") or "").strip()

        if not creator_id or not verification_text:
            return {
                "error": "Both 'creator_id' and 'verification_text' are required."
            }, 400

        verification_result = analyze_submission(
            verification_text,
            creator_id,
            content_type="verification_text",
            verified=False,
        )
        qualifies = (
            verification_result["attribution"] == "likely_human"
            and verification_result["confidence"] <= 0.38
        )

        if qualifies:
            verify_creator(
                creator_id,
                verification_result["content_id"],
                verification_result["confidence"],
                verification_result["timestamp"],
            )

        return jsonify(
            {
                "creator_id": creator_id,
                "verified": qualifies,
                "verification_content_id": verification_result["content_id"],
                "confidence": verification_result["confidence"],
                "attribution": verification_result["attribution"],
                "label": (
                    "Verified human creator badge granted."
                    if qualifies
                    else "Verification sample did not qualify for the verified human badge."
                ),
            }
        ), 200

    @app.get("/log")
    def get_log() -> tuple[dict, int]:
        return jsonify({"entries": get_recent_log_entries()}), 200

    @app.get("/content/<content_id>")
    def get_content_details(content_id: str) -> tuple[dict, int]:
        content = get_content(content_id)
        if content is None:
            return {"error": "Content not found."}, 404
        return jsonify(content), 200

    @app.get("/dashboard")
    def dashboard() -> str:
        return render_template("dashboard.html", metrics=get_dashboard_metrics())

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
