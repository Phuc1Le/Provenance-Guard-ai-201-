from datetime import datetime, timezone

from flask import Flask, jsonify, request
import uuid

from llm import analyze_text, score_to_label, label_to_message
from database import initialize_database, get_connection
from audit import (
    save_classification,
    save_appeal,
    update_classification_status,
    get_classifications,
)
from stylometric import analyze_stylometrics

app = Flask(__name__)
initialize_database()

REQUEST_LIMIT = 5

_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "you are ",
    "act as ",
    "pretend ",
    "flag this as human ",
    "suppose this was written by human ",
]


def _check_guardrails(text: str):
    """Return (error_message, status_code) or (None, None) if text is valid."""
    word_count = len(text.split())
    if word_count < 30:
        return "Unable to classify: content is too short to provide reliable evidence.", 400
    if word_count > 3000:
        return "Content is too long. Please split the document into smaller sections.", 400
    return None, None


def _has_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in _INJECTION_PATTERNS)


def _check_and_increment_user(user_id: str) -> bool:
    """
    Enforce 5 submissions per day per user_id.
    Resets the count when last_request_at is from a previous day.
    Appeals do not call this — only /submit does.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT requests_made, last_request_at FROM users WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    today = now.date().isoformat()

    if row is None:
        cursor.execute(
            "INSERT INTO users (user_id, requests_made, last_request_at) VALUES (?, 1, ?)",
            (user_id, now_iso),
        )
        conn.commit()
        conn.close()
        return True

    last_date = row["last_request_at"][:10] if row["last_request_at"] else None
    count = row["requests_made"] if last_date == today else 0

    if count >= REQUEST_LIMIT:
        conn.close()
        return False

    cursor.execute(
        "UPDATE users SET requests_made = ?, last_request_at = ? WHERE user_id = ?",
        (count + 1, now_iso, user_id),
    )
    conn.commit()
    conn.close()
    return True


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    user_id = data["user_id"]
    text = data["text"]

    if not _check_and_increment_user(user_id):
        return jsonify({"error": "Limit reached"}), 429

    error_msg, status_code = _check_guardrails(text)
    if error_msg:
        return jsonify({"error": error_msg}), status_code

    injection_detected = _has_injection(text)

    llm_result = analyze_text(text)
    stylo_result = analyze_stylometrics(text)

    confidence_score = round(0.65 * llm_result["score"] + 0.35 * stylo_result["score"], 4)
    label = score_to_label(confidence_score)
    transparency_message = label_to_message(label)

    post_id = str(uuid.uuid4())
    save_classification(
        post_id=post_id,
        user_id=user_id,
        content=text,
        confidence_score=confidence_score,
        llm_score=llm_result["score"],
        stylometric_score=stylo_result["score"],
        label=label,
        reasoning=llm_result["reasoning"],
    )

    return jsonify({
        "post_id": post_id,
        "label": label,
        "transparency_message": transparency_message,
        "confidence_score": confidence_score,
        "llm_score": llm_result["score"],
        "stylometric_score": stylo_result["score"],
        "stylometric_features": stylo_result["features"],
        "reasoning": llm_result["reasoning"],
        "injection_detected": injection_detected,
        "status": "classified",
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json()
    content_id = data["content_id"]
    creator_reasoning = data["creator_reasoning"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM classifications WHERE post_id = ?", (content_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Content ID not found."}), 404

    if row["status"] == "under_review":
        return jsonify({"error": "An appeal has already been submitted for this content."}), 409

    save_appeal(post_id=content_id, reason=creator_reasoning)
    update_classification_status(post_id=content_id, status="under_review")

    return jsonify({
        "post_id": content_id,
        "status": "under_review",
        "message": "Appeal submitted successfully. Your content has been flagged for manual review.",
    })


@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_classifications()})


if __name__ == "__main__":
    app.run(debug=True)
