"""Opt-in PostgreSQL regression checks in a disposable local database.

Run with VIDEO_USE_TEST_POSTGRES=1. Never connects to production.
"""

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

MIGRATION = (
    Path(__file__).parents[3]
    / "studio/migrations/20261001173820_narration-allowance.sql"
)
USER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
INACTIVE = "00000000-0000-0000-0000-000000000003"


@pytest.fixture(scope="module")
def database():
    if os.getenv("VIDEO_USE_TEST_POSTGRES") != "1" or not shutil.which("psql"):
        pytest.skip("Set VIDEO_USE_TEST_POSTGRES=1 for local PostgreSQL checks")
    name = "video_use_allowance_" + uuid4().hex
    roles = ["vpa_anon_" + uuid4().hex, "vpa_auth_" + uuid4().hex]

    def execute(query, *, db=name, check=True):
        result = subprocess.run(
            [
                "psql",
                "-X",
                "-h",
                "localhost",
                "-p",
                "5432",
                "-d",
                db,
                "-v",
                "ON_ERROR_STOP=1",
                "-A",
                "-t",
            ],
            input=query,
            text=True,
            capture_output=True,
            timeout=15,
        )
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result

    execute(f"CREATE DATABASE {name};", db="postgres")
    try:
        execute(
            "\n".join(f"CREATE ROLE {role} NOLOGIN;" for role in roles), db="postgres"
        )
        execute(f"""
CREATE TABLE public.vp_members(id uuid PRIMARY KEY,active boolean,is_owner boolean);
CREATE TABLE public.vp_usage(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),owner uuid REFERENCES public.vp_members,
 kind text,amount bigint CHECK(amount>=0),request_id text,settled boolean DEFAULT false,
 created timestamptz DEFAULT now(),UNIQUE(owner,kind,request_id));
INSERT INTO public.vp_members VALUES('{USER}',true,true),('{OTHER}',true,false),('{INACTIVE}',false,false);
""")
        # Rename only roles to avoid modifying other local applications' roles.
        migration = MIGRATION.read_text().replace(
            "PUBLIC,anon,authenticated", "PUBLIC," + ",".join(roles)
        )
        execute(migration)
        yield execute, roles
    finally:
        execute(f"DROP DATABASE IF EXISTS {name};", db="postgres", check=False)
        for role in roles:
            execute(f"DROP ROLE IF EXISTS {role};", db="postgres", check=False)


@pytest.fixture
def sql(database):
    execute, _ = database
    execute("TRUNCATE public.vp_usage;")
    return execute


def report(sql, uid=USER):
    return json.loads(sql(f"SELECT public.vp_narration_allowance('{uid}');").stdout)


def test_sql_counts_settled_reserved_and_utc_day_without_writes(sql):
    sql(f"""
INSERT INTO public.vp_usage(owner,kind,amount,request_id,settled,created) VALUES
 ('{USER}','narrate',600,'committed',true,now()),
 ('{USER}','narrate',200,'pending',false,now()),
 ('{USER}','narrate',50,'legacy-null',null,now()),
 ('{OTHER}','narrate',300,'shared',true,now()),
 ('{USER}','narrate',1900,'yesterday',true,date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' - interval '1 second'),
 ('{USER}','compute',100,'different-resource',false,now());
""")
    result = report(sql)
    assert result["user"] == {"limit": 2000, "committed": 600, "reserved": 250}
    assert result["shared"] == {"limit": 10000, "committed": 900, "reserved": 250}
    assert sql("SELECT count(*) FROM public.vp_usage;").stdout.strip() == "6"
    result = json.loads(
        sql(
            f"SET TIME ZONE 'America/Los_Angeles'; SELECT public.vp_narration_allowance('{USER}');"
        ).stdout.splitlines()[-1]
    )
    reset = datetime.fromisoformat(result["resets_at"]).astimezone(timezone.utc)
    assert (reset.hour, reset.minute, reset.second) == (0, 0, 0)


def test_sql_admission_and_exact_retries_use_same_limits(sql):
    query = f"SELECT public.vp_reserve('{USER}','narrate',2000,'exact');"
    assert sql(query).stdout.strip() == sql(query).stdout.strip()
    failed = sql(f"SELECT public.vp_reserve('{USER}','narrate',1,'over');", check=False)
    assert failed.returncode and "narrate allowance reached" in failed.stderr
    assert report(sql)["user"]["reserved"] == 2000
    assert sql("SELECT count(*) FROM public.vp_usage;").stdout.strip() == "1"
    sql("UPDATE public.vp_usage SET settled=true;")
    assert report(sql)["user"] == {"limit": 2000, "committed": 2000, "reserved": 0}


def test_sql_shared_limit_invalid_resource_and_inactive_member(sql):
    sql(
        f"INSERT INTO public.vp_usage(owner,kind,amount,request_id) VALUES('{OTHER}','narrate',9900,'other-usage');"
    )
    failed = sql(
        f"SELECT public.vp_reserve('{USER}','narrate',101,'shared-over');", check=False
    )
    assert failed.returncode and "narrate allowance reached" in failed.stderr
    sql(f"SELECT public.vp_reserve('{USER}','narrate',100,'shared-exact');")
    for query, message in (
        (
            f"SELECT public.vp_reserve('{USER}','other',1,'unknown');",
            "Unknown allowance",
        ),
        (
            f"SELECT public.vp_reserve('{USER}','narrate',-1,'negative');",
            "Invalid allowance",
        ),
        (
            f"SELECT public.vp_reserve('{INACTIVE}','narrate',1,'inactive');",
            "Active invitation required",
        ),
        (
            f"SELECT public.vp_narration_allowance('{INACTIVE}');",
            "Active invitation required",
        ),
    ):
        result = sql(query, check=False)
        assert result.returncode and message in result.stderr


def test_sql_concurrent_admission_never_overspends(sql):
    def reserve(index):
        return sql(
            f"SELECT public.vp_reserve('{USER}','narrate',1200,'race-{index}');",
            check=False,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(reserve, range(2)))
    assert sum(result.returncode == 0 for result in responses) == 1
    assert report(sql)["user"]["reserved"] == 1200


def test_sql_original_limits_and_function_privileges(sql, database):
    _, roles = database
    query = f"SELECT resource||':'||user_limit||':'||global_limit FROM unnest(ARRAY['compute','storage','transcribe','narrate']) resource CROSS JOIN LATERAL public.vp_allowance_limits('{USER}',resource);"
    assert sql(query).stdout.splitlines() == [
        "compute:3600:7200",
        "storage:5000000000:6000000000",
        "transcribe:1800:9000",
        "narrate:2000:10000",
    ]
    for role in roles:
        for signature in (
            "vp_allowance_limits(uuid,text)",
            "vp_narration_allowance(uuid)",
            "vp_reserve(uuid,text,bigint,text)",
        ):
            assert (
                sql(
                    f"SELECT has_function_privilege('{role}','public.{signature}','EXECUTE');"
                ).stdout.strip()
                == "f"
            )
