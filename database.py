import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "knowledgeping.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS settings (key   TEXT PRIMARY KEY, value TEXT NOT NULL)""")

    c.execute("""CREATE TABLE IF NOT EXISTS topics (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT    NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1)""")

    c.execute("""CREATE TABLE IF NOT EXISTS history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            topic     TEXT NOT NULL,
            type      TEXT NOT NULL,   -- 'lesson' | 'quiz'
            content   TEXT NOT NULL,
            timestamp TEXT NOT NULL)""")

    defaults = {
        "model":            "qwen3.5:0.8b",
        "interval_minutes": "15",
        "enabled":          "1",
    }

    for key, value in defaults.items():
        c.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    seed_topics = [
        "ordering food",
        "asking a stranger for directions",
        "checking into a hotel",
        "making a phone call",
        "buying a bus ticket",
        "describing your morning routine",
        "Introducing yourself (name, where you live, job/study)",
        "Shopping for clothes (asking for size, color, price)",
        "At the pharmacy (asking for headache medicine, describing a symptom)",
        "Ordering a taxi/rideshare (telling your location, destination)",
        "Complaining about a problem (wrong order, broken item – simple phrases)",
        "Talking about the weather (too hot/cold, raining, nice day)",
        "Making weekend plans (suggesting a movie, park, or café)",
        "At the doctor’s office (saying “my head hurts,” “I feel sick”)",
        "Asking for help at work/school (Can you show me? I don’t understand.)",
        "Paying a bill (asking for the check, splitting payment)",

    ]
    for t in seed_topics:
        c.execute("INSERT OR IGNORE INTO topics (name) VALUES (?)", (t,))

    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = _connect()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn = _connect()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_active_topics() -> list[str]:
    conn = _connect()
    rows = conn.execute("SELECT name FROM topics WHERE active = 1 ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def get_all_topics() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT id, name, active FROM topics ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_topic(name: str) -> None:
    conn = _connect()
    conn.execute("INSERT OR IGNORE INTO topics (name, active) VALUES (?, 1)", (name.strip(),))
    conn.commit()
    conn.close()


def delete_topic(topic_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()


def set_topic_active(topic_id: int, active: bool) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE topics SET active = ? WHERE id = ?",
        (1 if active else 0, topic_id),
    )
    conn.commit()
    conn.close()


def log_session(topic: str, type_: str, content: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO history (topic, type, content, timestamp) VALUES (?, ?, ?, ?)",
        (topic, type_, content, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 30) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM history ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_history() -> None:
    conn = _connect()
    conn.execute("DELETE FROM history")
    conn.commit()
    conn.close()