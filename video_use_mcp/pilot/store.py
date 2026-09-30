"""Parameterized InsForge REST persistence and private object transfer.

The coordinator owns writes. Browser users receive only owner-scoped reads;
atomic admission and budget functions live in the database migration.
"""

import json
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet


def ident():
    return str(uuid.uuid4())


class Store:
    def __init__(self, config):
        self.config = config
        self.vault = Fernet(config.encryption_key.encode())
        self.http = httpx.Client(
            base_url=config.insforge_url,
            timeout=45,
            headers={"Authorization": "Bearer " + config.api_key},
        )

    def request(self, method, path, **kwargs):
        r = self.http.request(method, path, **kwargs)
        if r.is_error:
            # Never propagate credentials, URLs with signatures, or raw request bodies.
            detail = (
                r.json().get("message", "")
                if "json" in r.headers.get("content-type", "")
                else ""
            )
            raise ValueError(
                f"Storage/database request failed ({r.status_code}): {detail[:250]}"
            )
        return r.json() if r.content else None

    def sql(self, query, *params):
        return self.request(
            "POST",
            "/api/database/advance/rawsql",
            json={"query": query, "params": list(params)},
        )["rows"]

    def put(self, kind, key, value, ttl=None):
        self.sql(
            "INSERT INTO public.vp_kv(kind,key,value,expires) VALUES ($1,$2,$3,$4) "
            "ON CONFLICT(kind,key) DO UPDATE SET value=excluded.value,expires=excluded.expires",
            kind,
            key,
            self.vault.encrypt(json.dumps(value).encode()).decode(),
            time.time() + ttl if ttl else None,
        )

    def get(self, kind, key, *, consume=False):
        rows = self.sql(
            (
                "DELETE FROM public.vp_kv WHERE kind=$1 AND key=$2 RETURNING *"
                if consume
                else "SELECT * FROM public.vp_kv WHERE kind=$1 AND key=$2"
            ),
            kind,
            key,
        )
        if not rows or (rows[0]["expires"] and rows[0]["expires"] < time.time()):
            return None
        return json.loads(self.vault.decrypt(rows[0]["value"].encode()))

    def delete(self, kind, key):
        self.sql("DELETE FROM public.vp_kv WHERE kind=$1 AND key=$2", kind, key)

    def identity(self, bearer):
        r = self.http.get(
            "/api/auth/sessions/current", headers={"Authorization": "Bearer " + bearer}
        )
        if r.status_code != 200:
            raise PermissionError("Sign in again")
        user = r.json()["user"]
        if user.get("emailVerified") is False:
            raise PermissionError("Verify your email first")
        return user

    def user(self, uid):
        rows = self.sql("SELECT * FROM public.vp_members WHERE id=$1 AND active", uid)
        return rows[0] if rows else None

    def member(self, uid):
        value = self.user(uid)
        if not value:
            raise PermissionError("An active pilot invitation is required")
        return value

    def project(self, uid, pid):
        self.member(uid)
        rows = self.sql(
            "SELECT * FROM public.vp_projects WHERE id=$1 AND owner=$2", pid, uid
        )
        if not rows:
            raise PermissionError("Project not found")
        return rows[0]

    def reserve(self, uid, kind, amount, key):
        return self.sql(
            "SELECT public.vp_reserve($1::uuid,$2,$3::bigint,$4) AS id",
            uid,
            kind,
            amount,
            key,
        )[0]["id"]

    def settle(self, rid, amount):
        self.sql(
            "UPDATE public.vp_usage SET amount=$2,settled=true WHERE id=$1",
            rid,
            max(0, int(amount)),
        )

    def task(self, uid, tid):
        self.member(uid)
        rows = self.sql(
            "SELECT * FROM public.vp_tasks WHERE id=$1 AND owner=$2", tid, uid
        )
        if not rows:
            raise PermissionError("Task not found")
        return rows[0]

    def object_path(self, key):
        return f"/api/storage/buckets/{self.config.bucket}/objects/" + quote(
            key, safe="/"
        )

    def upload(self, key, path, content_type="application/octet-stream"):
        path = Path(path)
        strategy = self.request(
            "POST",
            f"/api/storage/buckets/{self.config.bucket}/upload-strategy",
            json={
                "filename": key,
                "size": path.stat().st_size,
                "contentType": content_type,
            },
        )
        with path.open("rb") as stream:
            if strategy["method"] == "presigned":
                with httpx.Client(timeout=300) as external:
                    r = external.post(
                        strategy["uploadUrl"],
                        data=strategy["fields"],
                        files={"file": (path.name, stream, content_type)},
                    )
                    r.raise_for_status()
                return self.request(
                    "POST",
                    strategy["confirmUrl"],
                    json={"size": path.stat().st_size, "contentType": content_type},
                )
            return self.request(
                "PUT",
                strategy["uploadUrl"],
                files={"file": (path.name, stream, content_type)},
                timeout=300,
            )

    def download(self, key, target):
        strategy = self.request(
            "GET",
            f"/api/storage/buckets/{self.config.bucket}/download-strategy/objects/"
            + quote(key, safe="/"),
        )
        url = strategy["url"]
        # Do not forward admin authorization to a signed object-store URL.
        with httpx.Client(timeout=300, follow_redirects=True) as external:
            headers = (
                {"Authorization": "Bearer " + self.config.api_key}
                if url.startswith("/")
                else {}
            )
            with external.stream(
                "GET",
                self.config.insforge_url + url if url.startswith("/") else url,
                headers=headers,
            ) as r:
                r.raise_for_status()
                with Path(target).open("wb") as stream:
                    for chunk in r.iter_bytes():
                        stream.write(chunk)

    def remove_object(self, key):
        return self.request("DELETE", self.object_path(key))
