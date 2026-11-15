from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ScheduledJob:
    id: str
    account_alias: str
    run_at: str  # ISO8601 UTC
    job_type: str
    payload: dict[str, Any]
    status: str  # pending | running | done | failed
    created_at: str
    error: str | None = None
    result: dict[str, Any] | None = None


class SchedulerStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    account_alias TEXT NOT NULL,
                    run_at TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    error TEXT,
                    result TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_run ON jobs(status, run_at)")
            conn.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def add_job(
        self,
        *,
        account_alias: str,
        run_at: datetime,
        job_type: str,
        payload: dict[str, Any],
    ) -> ScheduledJob:
        jid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        run_at_iso = run_at.astimezone(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs(id,account_alias,run_at,job_type,payload,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (jid, account_alias, run_at_iso, job_type, json.dumps(payload), "pending", now),
            )
            conn.commit()
        return ScheduledJob(
            id=jid,
            account_alias=account_alias,
            run_at=run_at_iso,
            job_type=job_type,
            payload=payload,
            status="pending",
            created_at=now,
        )

    def list_jobs(self, *, status: str | None = None, account: str | None = None) -> list[ScheduledJob]:
        q = "SELECT * FROM jobs WHERE 1=1"
        args: list[Any] = []
        if status:
            q += " AND status = ?"
            args.append(status)
        if account:
            q += " AND account_alias = ?"
            args.append(account)
        q += " ORDER BY run_at ASC"
        with self._connect() as conn:
            rows = conn.execute(q, args).fetchall()
        return [self._row_to_job(r) for r in rows]

    def due_jobs(self, *, now: datetime | None = None) -> list[ScheduledJob]:
        now = now or datetime.now(timezone.utc)
        now_iso = now.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'pending' AND run_at <= ? ORDER BY run_at ASC",
                (now_iso,),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def update_status(
        self,
        job_id: str,
        *,
        status: str,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ?, result = ? WHERE id = ?",
                (status, error, json.dumps(result) if result else None, job_id),
            )
            conn.commit()

    def _row_to_job(self, row: sqlite3.Row) -> ScheduledJob:
        return ScheduledJob(
            id=row["id"],
            account_alias=row["account_alias"],
            run_at=row["run_at"],
            job_type=row["job_type"],
            payload=json.loads(row["payload"]),
            status=row["status"],
            created_at=row["created_at"],
            error=row["error"],
            result=json.loads(row["result"]) if row["result"] else None,
        )
