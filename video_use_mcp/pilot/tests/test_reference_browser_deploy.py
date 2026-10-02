"""Network and deployment boundaries for isolated reference research."""

from ipaddress import ip_address, ip_network
import sqlite3
from types import SimpleNamespace

import pytest

from video_use_mcp.pilot.deploy import ensure_quiet
from video_use_mcp.pilot.reference_browser_image import public_ipv4_allowlist


@pytest.mark.parametrize(
    "address",
    [
        "0.0.0.0",
        "10.0.0.1",
        "100.64.0.1",
        "100.127.255.255",
        "127.0.0.1",
        "169.254.169.254",
        "172.16.0.1",
        "172.31.255.255",
        "192.0.0.1",
        "192.0.2.1",
        "192.88.99.2",
        "192.168.1.1",
        "198.18.0.1",
        "198.19.255.255",
        "198.51.100.1",
        "203.0.113.1",
        "224.0.0.1",
        "239.255.255.255",
        "240.0.0.1",
        "255.255.255.255",
        "::1",
        "::ffff:127.0.0.1",
        "2001:4860:4860::8888",
    ],
)
def test_browser_egress_denies_nonpublic_and_ipv6_destinations(address):
    assert not any(
        ip_address(address) in ip_network(cidr) for cidr in public_ipv4_allowlist()
    )


@pytest.mark.parametrize(
    "address", ["1.1.1.1", "8.8.8.8", "104.18.32.7", "142.250.72.206"]
)
def test_browser_egress_allows_public_destinations(address):
    assert any(
        ip_address(address) in ip_network(cidr) for cidr in public_ipv4_allowlist()
    )


@pytest.fixture
def deployment_store():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("ATTACH DATABASE ':memory:' AS public")
    connection.executescript(
        "CREATE TABLE public.vp_tasks(id TEXT, status TEXT);"
        "CREATE TABLE public.vp_projects(id TEXT, sandbox_id TEXT);"
        "CREATE TABLE public.vp_kv(kind TEXT, key TEXT, expires REAL);"
    )

    def sql(query, *params):
        bindings = {str(index): value for index, value in enumerate(params, 1)}
        return [dict(row) for row in connection.execute(query, bindings).fetchall()]

    yield SimpleNamespace(sql=sql)
    connection.close()


def test_deploy_refuses_active_reference_browser_between_calls(
    deployment_store, monkeypatch
):
    monkeypatch.setattr("video_use_mcp.pilot.deploy.time.time", lambda: 1000)
    deployment_store.sql(
        "INSERT INTO public.vp_kv VALUES ($1,$2,$3)",
        "reference_browser_session",
        "active-project",
        1100,
    )
    with pytest.raises(RuntimeError, match="reference browser session is still active"):
        ensure_quiet(deployment_store)


def test_deploy_ignores_expired_reference_browser_records(deployment_store, monkeypatch):
    monkeypatch.setattr("video_use_mcp.pilot.deploy.time.time", lambda: 1000)
    for kind, project, expires in (
        ("reference_browser_session", "expired", 900),
        ("reference_browser_session", "just-expired", 1000),
        ("reference_browser_session", "missing-lease", None),
        ("other-kind", "unrelated", 1100),
    ):
        deployment_store.sql(
            "INSERT INTO public.vp_kv VALUES ($1,$2,$3)", kind, project, expires
        )
    ensure_quiet(deployment_store)
