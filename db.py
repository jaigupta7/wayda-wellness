import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "wellness.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            created_at TEXT,
            extracted_json TEXT,
            confirmed_json TEXT,
            status TEXT DEFAULT 'draft',
            report_filename TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_extraction(client_name: str, extracted: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO clients (client_name, created_at, extracted_json, status) VALUES (?, ?, ?, 'draft')",
        (client_name, datetime.now().isoformat(), json.dumps(extracted)),
    )
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id


def update_confirmed(record_id: int, confirmed: dict):
    conn = get_conn()
    conn.execute(
        "UPDATE clients SET confirmed_json = ?, status = 'confirmed' WHERE id = ?",
        (json.dumps(confirmed), record_id),
    )
    conn.commit()
    conn.close()


def mark_report_generated(record_id: int, filename: str):
    conn = get_conn()
    conn.execute(
        "UPDATE clients SET report_filename = ?, status = 'completed' WHERE id = ?",
        (filename, record_id),
    )
    conn.commit()
    conn.close()


def get_record(record_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (record_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_records():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, client_name, created_at, status, report_filename FROM clients ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_record(record_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM clients WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
