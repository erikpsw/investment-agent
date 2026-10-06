"""Durable local screening results with bounded workers and expiring leases."""
from contextlib import contextmanager
import json
from pathlib import Path
import secrets
import sqlite3
import time


class JobStore:
    def __init__(self, path: Path, capacity=2, lease_seconds=90, retention_seconds=86400):
        self.path = Path(path)
        self.capacity = capacity
        self.lease_seconds = lease_seconds
        self.retention_seconds = retention_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, request TEXT NOT NULL, response TEXT, message TEXT, updated REAL NOT NULL)")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def maintain(self, db, now):
        db.execute("UPDATE jobs SET status='interrupted', message=?, updated=? WHERE status='running' AND updated < ?", ("筛选服务已中断，请重新提交；没有生成完整结果。", now, now-self.lease_seconds))
        db.execute("DELETE FROM jobs WHERE status != 'running' AND updated < ?", (now-self.retention_seconds,))

    def create(self, request, now=None, job_id=None):
        now = time.time() if now is None else now
        job_id = job_id or secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self.maintain(db, now)
            existing = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if existing:
                if json.loads(existing["request"]) != request:
                    raise ValueError("different request")
                return {**self.decode(existing), "created": False}
            count = db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]
            if count >= self.capacity:
                raise RuntimeError("capacity")
            db.execute("INSERT INTO jobs (id,status,request,updated) VALUES (?, 'running', ?, ?)", (job_id, json.dumps(request, ensure_ascii=False, allow_nan=False), now))
        return {**self.get(job_id, now), "created": True}

    def get(self, job_id, now=None):
        now = time.time() if now is None else now
        with self.connection() as db:
            self.maintain(db, now)
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        return self.decode(row)

    @staticmethod
    def decode(row):
        return {"id": row["id"], "status": row["status"], "request": json.loads(row["request"]), "response": json.loads(row["response"]) if row["response"] else None, "message": row["message"]}

    def heartbeat(self, job_id, now=None):
        now = time.time() if now is None else now
        with self.connection() as db:
            return db.execute("UPDATE jobs SET updated=? WHERE id=? AND status='running'", (now, job_id)).rowcount == 1

    def finish(self, job_id, response, now=None):
        now = time.time() if now is None else now
        with self.connection() as db:
            return db.execute("UPDATE jobs SET status='completed', response=?, updated=? WHERE id=? AND status='running'", (json.dumps(response, ensure_ascii=False, allow_nan=False), now, job_id)).rowcount == 1

    def fail(self, job_id, message, now=None):
        now = time.time() if now is None else now
        with self.connection() as db:
            return db.execute("UPDATE jobs SET status='failed', message=?, updated=? WHERE id=? AND status='running'", (message, now, job_id)).rowcount == 1
