import json
from datetime import datetime, timezone

from database import get_connection


def save_classification(
    post_id,
    user_id,
    content,
    confidence_score,
    llm_score,
    stylometric_score,
    label,
    reasoning,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO classifications
        (
            post_id,
            user_id,
            content,
            confidence_score,
            llm_score,
            stylometric_score,
            label,
            reasoning,
            status,
            timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        post_id,
        user_id,
        content,
        confidence_score,
        llm_score,
        stylometric_score,
        label,
        json.dumps(reasoning),
        "classified",
        datetime.now(timezone.utc).isoformat(),
    ))

    conn.commit()
    conn.close()


def save_appeal(post_id, reason):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO appeals (post_id, reason, timestamp)
        VALUES (?, ?, ?)
    """, (post_id, reason, datetime.now(timezone.utc).isoformat()))

    conn.commit()
    conn.close()


def update_classification_status(post_id, status):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE classifications SET status = ? WHERE post_id = ?
    """, (status, post_id))

    conn.commit()
    conn.close()


def get_classifications():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.*,
            a.reason   AS appeal_reasoning,
            a.timestamp AS appeal_timestamp
        FROM classifications c
        LEFT JOIN appeals a ON c.post_id = a.post_id
        ORDER BY c.timestamp DESC
    """)

    rows = []
    for row in cursor.fetchall():
        entry = dict(row)
        if entry.get("reasoning"):
            entry["reasoning"] = json.loads(entry["reasoning"])
        rows.append(entry)

    conn.close()
    return rows
