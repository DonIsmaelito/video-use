"""One-process SQLite persistence; media is outside the database, keys are encrypted."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet


def identifier(prefix: str) -> str:
    return prefix + "_" + secrets.token_hex(12)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Store:
    def __init__(self, root: Path, encryption_key: str = ""):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "service.sqlite3"
        key_path = self.root / "vault.key"
        if not encryption_key:
            try:
                with key_path.open("xb") as stream:
                    os.chmod(key_path, 0o600)
                    stream.write(Fernet.generate_key())
            except FileExistsError:
                pass
            encryption_key = key_path.read_text().strip()
        self.vault = Fernet(encryption_key.encode())
        self.passwords = PasswordHasher()
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kv (
                    kind TEXT NOT NULL, key TEXT NOT NULL, value BLOB NOT NULL,
                    expires REAL, PRIMARY KEY(kind,key)
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, project TEXT NOT NULL, name TEXT NOT NULL,
                    path TEXT NOT NULL, size INTEGER NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, project TEXT NOT NULL, owner TEXT NOT NULL,
                    prompt TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL,
                    updated REAL NOT NULL, result TEXT, error TEXT,
                    idempotency_key TEXT, UNIQUE(owner,idempotency_key)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_project_job ON jobs(project)
                    WHERE status IN ('queued','running','cancelling');
                CREATE TABLE IF NOT EXISTS job_usage (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, created REAL NOT NULL
                );
                INSERT OR IGNORE INTO job_usage SELECT id,owner,created FROM jobs;
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT NOT NULL,
                    created REAL NOT NULL, message TEXT NOT NULL
                );
            """)
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, kind, key, value, ttl=None):
        payload = self.vault.encrypt(json.dumps(value).encode())
        with self.db() as db:
            db.execute(
                "INSERT OR REPLACE INTO kv VALUES (?,?,?,?)",
                (kind, key, payload, time.time() + ttl if ttl else None),
            )

    def get(self, kind, key, *, consume=False):
        with self.db() as db:
            if consume:
                row = db.execute(
                    "DELETE FROM kv WHERE kind=? AND key=? RETURNING *", (kind, key)
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT * FROM kv WHERE kind=? AND key=?", (kind, key)
                ).fetchone()
        if row is None or (row["expires"] and row["expires"] < time.time()):
            return None
        return json.loads(self.vault.decrypt(row["value"]))

    def delete(self, kind, key):
        with self.db() as db:
            db.execute("DELETE FROM kv WHERE kind=? AND key=?", (kind, key))

    def create_user(self, username, password):
        uid = identifier("user")
        with self.db() as db:
            db.execute(
                "INSERT INTO users VALUES (?,?,?,?)",
                (uid, username.lower(), self.passwords.hash(password), time.time()),
            )
        return uid

    def login(self, username, password):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM users WHERE username=?", (username.lower(),)
            ).fetchone()
        # Run a password hash even for unknown users to avoid a cheap timing oracle.
        encoded = row["password"] if row else self.passwords.hash(secrets.token_hex(16))
        try:
            valid = self.passwords.verify(encoded, password)
        except VerificationError:
            valid = False
        return row["id"] if row and valid else None

    def user(self, uid):
        with self.db() as db:
            row = db.execute(
                "SELECT id,username FROM users WHERE id=?", (uid,)
            ).fetchone()
        return dict(row) if row else None

    def project(self, uid, pid):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM projects WHERE id=? AND owner=?", (pid, uid)
            ).fetchone()
            assets = (
                db.execute(
                    "SELECT id,name,size,created FROM assets WHERE project=? ORDER BY created",
                    (pid,),
                ).fetchall()
                if row
                else []
            )
            jobs = (
                db.execute(
                    "SELECT * FROM jobs WHERE project=? ORDER BY created DESC LIMIT 30",
                    (pid,),
                ).fetchall()
                if row
                else []
            )
        if row is None:
            raise KeyError("Project not found")
        return {
            **dict(row),
            "assets": [dict(x) for x in assets],
            "jobs": [self.decode_job(x) for x in jobs],
        }

    def create_project(self, uid, title):
        pid = identifier("project")
        with self.db() as db:
            db.execute(
                "INSERT INTO projects VALUES (?,?,?,?)", (pid, uid, title, time.time())
            )
        return self.project(uid, pid)

    def latest_success(self, uid, pid):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE owner=? AND project=? AND status='succeeded' ORDER BY created DESC LIMIT 1",
                (uid, pid),
            ).fetchone()
        return self.decode_job(row) if row else None

    def projects(self, uid):
        with self.db() as db:
            return [
                dict(x)
                for x in db.execute(
                    "SELECT * FROM projects WHERE owner=? ORDER BY created DESC", (uid,)
                )
            ]

    def asset_rows(self, uid, pid):
        self.project(uid, pid)
        with self.db() as db:
            return [
                dict(x)
                for x in db.execute(
                    "SELECT * FROM assets WHERE project=? ORDER BY created", (pid,)
                )
            ]

    def user_bytes(self, uid):
        with self.db() as db:
            uploads = db.execute(
                "SELECT coalesce(sum(size),0) FROM assets JOIN projects ON assets.project=projects.id WHERE owner=?",
                (uid,),
            ).fetchone()[0]
            outputs = db.execute(
                "SELECT coalesce(sum(coalesce(json_extract(result,'$.size_bytes'),0)+coalesce(json_extract(result,'$.source_bytes'),0)),0) FROM jobs WHERE owner=?",
                (uid,),
            ).fetchone()[0]
            return uploads + outputs

    def add_asset(self, uid, pid, name, path, size):
        self.project(uid, pid)
        aid = identifier("asset")
        with self.db() as db:
            db.execute(
                "INSERT INTO assets VALUES (?,?,?,?,?,?)",
                (aid, pid, name, str(path), size, time.time()),
            )
        return {"id": aid, "name": name, "size": size}

    def remove_project(self, uid, pid):
        self.project(uid, pid)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM jobs WHERE project=? AND status IN ('queued','running','cancelling')",
                (pid,),
            ).fetchone():
                raise ValueError("Stop this project's active job before deleting it")
            jobs = [
                row[0]
                for row in db.execute("SELECT id FROM jobs WHERE project=?", (pid,))
            ]
            for jid in jobs:
                db.execute("DELETE FROM events WHERE job=?", (jid,))
            db.execute("DELETE FROM jobs WHERE project=?", (pid,))
            db.execute("DELETE FROM assets WHERE project=?", (pid,))
            db.execute("DELETE FROM projects WHERE id=? AND owner=?", (pid, uid))
        return jobs

    def remove_asset(self, uid, pid, aid):
        self.project(uid, pid)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM jobs WHERE project=? AND status IN ('queued','running','cancelling')",
                (pid,),
            ).fetchone():
                raise ValueError(
                    "Wait for this project's active job before removing media"
                )
            row = db.execute(
                "DELETE FROM assets WHERE id=? AND project=? RETURNING path", (aid, pid)
            ).fetchone()
        if row is None:
            raise KeyError("Media not found")
        return Path(row[0])

    def queue_job(self, uid, pid, prompt, key, daily_limit):
        self.project(uid, pid)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if key:
                old = db.execute(
                    "SELECT * FROM jobs WHERE owner=? AND idempotency_key=?", (uid, key)
                ).fetchone()
                if old:
                    if old["project"] != pid or old["prompt"] != prompt:
                        raise ValueError(
                            "That request ID was already used for a different job"
                        )
                    return self.decode_job(old)
            count = db.execute(
                "SELECT count(*) FROM job_usage WHERE owner=? AND created>?",
                (uid, time.time() - 86400),
            ).fetchone()[0]
            if count >= daily_limit:
                raise ValueError("Daily job limit reached. Try again later.")
            count = db.execute(
                "SELECT count(*) FROM jobs WHERE owner=? AND status IN ('queued','running','cancelling')",
                (uid,),
            ).fetchone()[0]
            if count >= 2:
                raise ValueError("Two jobs are already active. Wait for one to finish.")
            jid = identifier("job")
            now = time.time()
            try:
                db.execute(
                    "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (jid, pid, uid, prompt, "queued", now, now, None, None, key),
                )
                db.execute("INSERT INTO job_usage VALUES (?,?,?)", (jid, uid, now))
            except sqlite3.IntegrityError:
                raise ValueError("This project already has an active job") from None
        return self.job(uid, jid)

    @staticmethod
    def decode_job(row):
        result = dict(row)
        result["result"] = json.loads(result["result"]) if result["result"] else None
        return result

    def job(self, uid, jid):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE id=? AND owner=?", (jid, uid)
            ).fetchone()
            events = (
                db.execute(
                    "SELECT id,created,message FROM events WHERE job=? ORDER BY id DESC LIMIT 80",
                    (jid,),
                ).fetchall()
                if row
                else []
            )
        if row is None:
            raise KeyError("Job not found")
        return {**self.decode_job(row), "events": [dict(x) for x in reversed(events)]}

    def update_job(self, jid, status, *, result=None, error=None):
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET status=?,updated=?,result=?,error=? WHERE id=?",
                (
                    status,
                    time.time(),
                    json.dumps(result) if result else None,
                    error,
                    jid,
                ),
            )

    def event(self, jid, message):
        with self.db() as db:
            db.execute(
                "INSERT INTO events(job,created,message) VALUES (?,?,?)",
                (jid, time.time(), str(message)[:2000]),
            )

    def queued(self):
        with self.db() as db:
            return [
                dict(x)
                for x in db.execute(
                    "SELECT * FROM jobs WHERE status='queued' ORDER BY created"
                )
            ]

    def recover(self):
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET status='failed',error='The worker restarted. Your media is safe; start a new revision.',updated=? WHERE status IN ('running','cancelling')",
                (time.time(),),
            )
            db.execute(
                "DELETE FROM kv WHERE expires IS NOT NULL AND expires < ?",
                (time.time(),),
            )
