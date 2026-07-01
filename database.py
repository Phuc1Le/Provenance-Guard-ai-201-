import sqlite3

DATABASE_NAME = "provenance_guard.db"


def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        requests_made INTEGER NOT NULL DEFAULT 0,
        last_request_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS classifications (
        post_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        content TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        llm_score REAL,
        stylometric_score REAL,
        label TEXT NOT NULL,
        reasoning TEXT,
        status TEXT NOT NULL,
        timestamp TEXT NOT NULL,

        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appeals (
        post_id TEXT PRIMARY KEY,
        reason TEXT NOT NULL,
        timestamp TEXT NOT NULL,

        FOREIGN KEY (post_id) REFERENCES classifications(post_id)
    )
    """)

    conn.commit()
    _migrate(conn)
    conn.close()


def _migrate(conn):
    """Add columns that exist in the schema but are missing from older DB files."""
    cursor = conn.cursor()

    existing_cls = {row[1] for row in cursor.execute("PRAGMA table_info(classifications)")}
    for col, col_type in {
        "llm_score": "REAL",
        "stylometric_score": "REAL",
        "reasoning": "TEXT",
    }.items():
        if col not in existing_cls:
            cursor.execute(f"ALTER TABLE classifications ADD COLUMN {col} {col_type}")

    existing_usr = {row[1] for row in cursor.execute("PRAGMA table_info(users)")}
    if "last_request_at" not in existing_usr:
        cursor.execute("ALTER TABLE users ADD COLUMN last_request_at TEXT")

    existing_app = {row[1] for row in cursor.execute("PRAGMA table_info(appeals)")}
    if "timestamp" not in existing_app:
        cursor.execute("ALTER TABLE appeals ADD COLUMN timestamp TEXT")

    conn.commit()
