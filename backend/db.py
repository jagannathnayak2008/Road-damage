"""
RoadWatch AI - SQLite Database Interface
Handles storage and retrieval of road damage inspection reports.
"""

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

# Keep the existing database at the project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "reports.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection with row factory configured as dictionary-like Row."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes the database schema if it doesn't already exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                damage_type TEXT NOT NULL,
                pothole_count INTEGER DEFAULT 0,
                damage_percent REAL DEFAULT 0.0,
                severity TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                summary TEXT,
                recommended_action TEXT,
                user_description TEXT DEFAULT '',
                status TEXT DEFAULT 'Reported',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Create indexes for frequently queried columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_severity ON reports(severity);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);")
        conn.commit()


def insert_report(
    image_path: str,
    latitude: float,
    longitude: float,
    damage_type: str,
    pothole_count: int,
    damage_percent: float,
    severity: str,
    confidence: float,
    summary: str,
    recommended_action: str,
    user_description: str = "",
    status: str = "Reported",
    created_at: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Inserts a new road damage report into the database and returns the generated report ID."""
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reports (
                image_path, latitude, longitude, damage_type, pothole_count,
                damage_percent, severity, confidence, summary, recommended_action,
                user_description, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_path,
                latitude,
                longitude,
                damage_type,
                pothole_count,
                damage_percent,
                severity,
                confidence,
                summary,
                recommended_action,
                user_description,
                status,
                created_at,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_all_reports(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all reports sorted by creation date descending."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports ORDER BY created_at DESC, id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_report_by_id(report_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves a single report by its ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_report_status(report_id: int, new_status: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Updates the status of a specific report (e.g. Reported, Assigned, In Progress, Fixed)."""
    valid_statuses = {"Reported", "Assigned", "In Progress", "Fixed"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE reports SET status = ? WHERE id = ?",
            (new_status, report_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_report_counts(db_path: str = DEFAULT_DB_PATH) -> Dict[str, int]:
    """Returns summary counts: total, open, fixed, high_severity."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reports")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reports WHERE status != 'Fixed'")
        open_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reports WHERE status = 'Fixed'")
        fixed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reports WHERE severity = 'High'")
        high_severity = cursor.fetchone()[0]

        return {
            "total": total,
            "open": open_count,
            "fixed": fixed,
            "high_severity": high_severity,
        }


def filter_reports(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Filters reports by status and/or severity."""
    query = "SELECT * FROM reports WHERE 1=1"
    params: List[Any] = []

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)

    if severity and severity != "All":
        query += " AND severity = ?"
        params.append(severity)

    query += " ORDER BY created_at DESC, id DESC"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
