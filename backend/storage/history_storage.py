"""对话历史、评估报告与方法偏好持久化存储。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class HistoryStorage:
    """基于 SQLite 的历史存储。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else Path("data/history.db")
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    conversation_id TEXT,
                    query TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    steps_count INTEGER NOT NULL DEFAULT 0,
                    trajectory_id TEXT,
                    evaluation_id TEXT,
                    task_family TEXT NOT NULL DEFAULT '',
                    evaluation_score REAL NOT NULL DEFAULT 0,
                    evaluation_passed INTEGER NOT NULL DEFAULT 0,
                    evaluation_summary TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT 'unreviewed',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_reports (
                    id TEXT PRIMARY KEY,
                    analysis_record_id TEXT NOT NULL UNIQUE,
                    session_id TEXT,
                    trajectory_id TEXT,
                    task_family TEXT NOT NULL DEFAULT '',
                    final_score REAL NOT NULL DEFAULT 0,
                    passed INTEGER NOT NULL DEFAULT 0,
                    summary TEXT NOT NULL DEFAULT '',
                    report_json TEXT NOT NULL DEFAULT '{}',
                    review_status TEXT NOT NULL DEFAULT 'unreviewed',
                    review_label TEXT NOT NULL DEFAULT '',
                    review_comment TEXT NOT NULL DEFAULT '',
                    reviewed_by TEXT NOT NULL DEFAULT '',
                    associated_skill TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(analysis_record_id) REFERENCES analysis_records(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS method_preferences (
                    user_id TEXT NOT NULL,
                    family TEXT NOT NULL,
                    preferred_variant TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, family)
                )
                """
            )

            self._create_indexes(conn)
            self._ensure_legacy_columns(conn)
            conn.commit()

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_updated "
            "ON conversations(user_id, updated_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_session "
            "ON conversations(session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation "
            "ON messages(conversation_id, timestamp ASC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_user_created "
            "ON analysis_records(user_id, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_session "
            "ON analysis_records(session_id, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evaluations_skill_created "
            "ON evaluation_reports(associated_skill, created_at DESC)"
        )

    def _ensure_legacy_columns(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(conn, "analysis_records", "trajectory_id", "TEXT")
        self._ensure_column(conn, "analysis_records", "evaluation_id", "TEXT")
        self._ensure_column(conn, "analysis_records", "task_family", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "analysis_records", "evaluation_score", "REAL NOT NULL DEFAULT 0")
        self._ensure_column(conn, "analysis_records", "evaluation_passed", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "analysis_records", "evaluation_summary", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "analysis_records", "review_status", "TEXT NOT NULL DEFAULT 'unreviewed'")

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        existing_columns = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_conversations(self, user_id: str, offset: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        with self._connect() as conn:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE user_id = ?",
                    (user_id,),
                ).fetchone()[0]
            )
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "messages": [],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": int(row["message_count"] or 0),
            }
            for row in rows
        ], total

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                return None
            messages = conn.execute(
                """
                SELECT role, content, timestamp
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
        message_list = [
            {
                "role": item["role"],
                "content": item["content"],
                "timestamp": item["timestamp"],
            }
            for item in messages
        ]
        return {
            "id": row["id"],
            "title": row["title"],
            "messages": message_list,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": len(message_list),
        }

    def create_conversation(
        self,
        *,
        title: str,
        user_id: str = "default",
        session_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now().isoformat()
        conversation_id = conversation_id or f"{user_id}_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, user_id, session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, user_id, session_id, title, timestamp, timestamp),
            )
            conn.commit()
        return {
            "id": conversation_id,
            "title": title,
            "messages": [],
            "created_at": timestamp,
            "updated_at": timestamp,
            "message_count": 0,
        }

    def get_or_create_session_conversation(
        self,
        *,
        session_id: str,
        user_id: str = "default",
        title: str = "新对话",
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM conversations
                WHERE session_id = ? AND user_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (session_id, user_id),
            ).fetchone()
        if row is not None:
            conversation = self.get_conversation(str(row["id"]))
            if conversation is not None:
                return conversation
        return self.create_conversation(
            title=title,
            user_id=user_id,
            session_id=session_id,
            conversation_id=f"{user_id}_{session_id}",
        )

    def get_session_conversation(
        self,
        *,
        session_id: str,
        user_id: str = "default",
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM conversations
                WHERE session_id = ? AND user_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (session_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return self.get_conversation(str(row["id"]))

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        timestamp: str | None = None,
    ) -> dict[str, str]:
        message_time = timestamp or datetime.now().isoformat()
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if exists is None:
                raise KeyError(conversation_id)
            conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, role, content, message_time),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (message_time, conversation_id),
            )
            conn.commit()
        return {"role": role, "content": content, "timestamp": message_time}

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
        return cursor.rowcount > 0

    def list_analysis_records(self, user_id: str, offset: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        with self._connect() as conn:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM analysis_records WHERE user_id = ?",
                    (user_id,),
                ).fetchone()[0]
            )
            rows = conn.execute(
                """
                SELECT
                    id, session_id, conversation_id, query, intent, status, result_summary, created_at,
                    updated_at, steps_count, trajectory_id, evaluation_id, task_family,
                    evaluation_score, evaluation_passed, evaluation_summary, review_status
                FROM analysis_records
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        return [self._row_to_analysis_record(row) for row in rows], total

    def create_analysis_record(
        self,
        *,
        query: str,
        intent: str = "",
        status: str = "pending",
        result_summary: str = "",
        steps_count: int = 0,
        user_id: str = "default",
        session_id: str | None = None,
        conversation_id: str | None = None,
        trajectory_id: str | None = None,
        evaluation_id: str | None = None,
        task_family: str = "",
        evaluation_score: float = 0.0,
        evaluation_passed: bool = False,
        evaluation_summary: str = "",
        review_status: str = "unreviewed",
        record_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now().isoformat()
        analysis_id = record_id or f"analysis_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_records (
                    id, user_id, session_id, conversation_id, query, intent, status,
                    result_summary, steps_count, trajectory_id, evaluation_id, task_family,
                    evaluation_score, evaluation_passed, evaluation_summary, review_status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    user_id,
                    session_id,
                    conversation_id,
                    query,
                    intent,
                    status,
                    result_summary,
                    steps_count,
                    trajectory_id,
                    evaluation_id,
                    task_family,
                    evaluation_score,
                    1 if evaluation_passed else 0,
                    evaluation_summary,
                    review_status,
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
        return self.get_analysis_record(analysis_id) or {}

    def update_analysis_record(self, record_id: str, **updates: Any) -> dict[str, Any] | None:
        allowed_fields = {
            "intent",
            "status",
            "result_summary",
            "steps_count",
            "trajectory_id",
            "conversation_id",
            "session_id",
            "evaluation_id",
            "task_family",
            "evaluation_score",
            "evaluation_passed",
            "evaluation_summary",
            "review_status",
        }
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            if key in allowed_fields:
                assignments.append(f"{key} = ?")
                values.append(value)
        if not assignments:
            return self.get_analysis_record(record_id)
        assignments.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(record_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE analysis_records SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_analysis_record(record_id)

    def get_analysis_record(self, record_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id, session_id, conversation_id, query, intent, status, result_summary, created_at,
                    updated_at, steps_count, trajectory_id, evaluation_id, task_family,
                    evaluation_score, evaluation_passed, evaluation_summary, review_status
                FROM analysis_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_analysis_record(row)

    def get_latest_analysis_record_for_session(
        self,
        *,
        session_id: str,
        user_id: str = "default",
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM analysis_records
                WHERE session_id = ? AND user_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (session_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return self.get_analysis_record(str(row["id"]))

    def upsert_evaluation_report(
        self,
        *,
        analysis_record_id: str,
        session_id: str | None,
        trajectory_id: str | None,
        task_family: str,
        final_score: float,
        passed: bool,
        summary: str,
        report_json: dict[str, Any],
        associated_skill: str = "",
    ) -> dict[str, Any]:
        timestamp = datetime.now().isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, review_status, review_label, review_comment, reviewed_by, created_at "
                "FROM evaluation_reports WHERE analysis_record_id = ?",
                (analysis_record_id,),
            ).fetchone()

            if existing is None:
                evaluation_id = f"eval_{uuid.uuid4().hex[:12]}"
                created_at = timestamp
                review_status = "unreviewed"
                review_label = ""
                review_comment = ""
                reviewed_by = ""
                conn.execute(
                    """
                    INSERT INTO evaluation_reports (
                        id, analysis_record_id, session_id, trajectory_id, task_family, final_score,
                        passed, summary, report_json, review_status, review_label, review_comment,
                        reviewed_by, associated_skill, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evaluation_id,
                        analysis_record_id,
                        session_id,
                        trajectory_id,
                        task_family,
                        final_score,
                        1 if passed else 0,
                        summary,
                        json.dumps(report_json, ensure_ascii=False),
                        review_status,
                        review_label,
                        review_comment,
                        reviewed_by,
                        associated_skill,
                        created_at,
                        timestamp,
                    ),
                )
            else:
                evaluation_id = str(existing["id"])
                created_at = str(existing["created_at"])
                review_status = str(existing["review_status"] or "unreviewed")
                review_label = str(existing["review_label"] or "")
                review_comment = str(existing["review_comment"] or "")
                reviewed_by = str(existing["reviewed_by"] or "")
                conn.execute(
                    """
                    UPDATE evaluation_reports
                    SET session_id = ?, trajectory_id = ?, task_family = ?, final_score = ?,
                        passed = ?, summary = ?, report_json = ?, associated_skill = ?, updated_at = ?
                    WHERE analysis_record_id = ?
                    """,
                    (
                        session_id,
                        trajectory_id,
                        task_family,
                        final_score,
                        1 if passed else 0,
                        summary,
                        json.dumps(report_json, ensure_ascii=False),
                        associated_skill,
                        timestamp,
                        analysis_record_id,
                    ),
                )

            conn.execute(
                """
                UPDATE analysis_records
                SET evaluation_id = ?, task_family = ?, evaluation_score = ?, evaluation_passed = ?,
                    evaluation_summary = ?, review_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    evaluation_id,
                    task_family,
                    final_score,
                    1 if passed else 0,
                    summary,
                    review_status,
                    timestamp,
                    analysis_record_id,
                ),
            )
            conn.commit()

        return {
            "id": evaluation_id,
            "analysis_record_id": analysis_record_id,
            "session_id": session_id,
            "trajectory_id": trajectory_id,
            "task_family": task_family,
            "final_score": final_score,
            "passed": passed,
            "summary": summary,
            "report_json": report_json,
            "review_status": review_status,
            "review_label": review_label,
            "review_comment": review_comment,
            "reviewed_by": reviewed_by,
            "associated_skill": associated_skill,
            "created_at": created_at,
            "updated_at": timestamp,
        }

    def get_evaluation_report(self, analysis_record_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id, analysis_record_id, session_id, trajectory_id, task_family, final_score,
                    passed, summary, report_json, review_status, review_label, review_comment,
                    reviewed_by, associated_skill, created_at, updated_at
                FROM evaluation_reports
                WHERE analysis_record_id = ?
                """,
                (analysis_record_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_evaluation_report(row)

    def update_evaluation_review(
        self,
        analysis_record_id: str,
        *,
        review_status: str,
        review_label: str,
        review_comment: str = "",
        reviewed_by: str = "default",
    ) -> dict[str, Any] | None:
        timestamp = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE evaluation_reports
                SET review_status = ?, review_label = ?, review_comment = ?, reviewed_by = ?, updated_at = ?
                WHERE analysis_record_id = ?
                """,
                (review_status, review_label, review_comment, reviewed_by, timestamp, analysis_record_id),
            )
            if cursor.rowcount == 0:
                conn.commit()
                return None
            conn.execute(
                """
                UPDATE analysis_records
                SET review_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (review_status, timestamp, analysis_record_id),
            )
            conn.commit()
        return self.get_evaluation_report(analysis_record_id)

    def list_recent_evaluations_for_skill(self, skill_name: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, analysis_record_id, session_id, trajectory_id, task_family, final_score,
                    passed, summary, report_json, review_status, review_label, review_comment,
                    reviewed_by, associated_skill, created_at, updated_at
                FROM evaluation_reports
                WHERE associated_skill = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (skill_name, limit),
            ).fetchall()
        return [self._row_to_evaluation_report(row) for row in rows]

    def set_preferred_variant(
        self,
        *,
        user_id: str,
        family: str,
        preferred_variant: str,
    ) -> dict[str, Any]:
        timestamp = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO method_preferences (user_id, family, preferred_variant, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, family) DO UPDATE SET
                    preferred_variant = excluded.preferred_variant,
                    updated_at = excluded.updated_at
                """,
                (user_id, family, preferred_variant, timestamp),
            )
            conn.commit()
        return {
            "user_id": user_id,
            "family": family,
            "preferred_variant": preferred_variant,
            "updated_at": timestamp,
        }

    def get_preferred_variant(self, *, user_id: str, family: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT preferred_variant
                FROM method_preferences
                WHERE user_id = ? AND family = ?
                """,
                (user_id, family),
            ).fetchone()
        if row is None:
            return ""
        return str(row["preferred_variant"] or "")

    def list_preferred_variants(self, *, user_id: str) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT family, preferred_variant
                FROM method_preferences
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchall()
        return {str(row["family"]): str(row["preferred_variant"] or "") for row in rows}

    def reset(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM evaluation_reports")
            conn.execute("DELETE FROM analysis_records")
            conn.execute("DELETE FROM method_preferences")
            conn.execute("DELETE FROM conversations")
            conn.commit()

    def _row_to_analysis_record(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "conversation_id": row["conversation_id"],
            "query": row["query"],
            "intent": row["intent"],
            "status": row["status"],
            "result_summary": row["result_summary"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "steps_count": int(row["steps_count"] or 0),
            "trajectory_id": row["trajectory_id"] or "",
            "evaluation_id": row["evaluation_id"] or "",
            "task_family": row["task_family"] or "",
            "evaluation_score": float(row["evaluation_score"] or 0.0),
            "evaluation_passed": bool(row["evaluation_passed"]),
            "evaluation_summary": row["evaluation_summary"] or "",
            "review_status": row["review_status"] or "unreviewed",
        }

    def _row_to_evaluation_report(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(row["report_json"] or "{}")
        return {
            "id": row["id"],
            "analysis_record_id": row["analysis_record_id"],
            "session_id": row["session_id"],
            "trajectory_id": row["trajectory_id"] or "",
            "task_family": row["task_family"] or "",
            "final_score": float(row["final_score"] or 0.0),
            "passed": bool(row["passed"]),
            "summary": row["summary"] or "",
            "report_json": payload,
            "review_status": row["review_status"] or "unreviewed",
            "review_label": row["review_label"] or "",
            "review_comment": row["review_comment"] or "",
            "reviewed_by": row["reviewed_by"] or "",
            "associated_skill": row["associated_skill"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


_history_storage: HistoryStorage | None = None


def get_history_storage() -> HistoryStorage:
    global _history_storage
    if _history_storage is None:
        _history_storage = HistoryStorage()
    return _history_storage


def reset_history_storage() -> None:
    get_history_storage().reset()
