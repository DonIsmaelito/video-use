"""Credential-free Chromium image and public-network boundary for research."""

from ipaddress import ip_network

from video_use_mcp.config import ROOT


# Conservatively exclude private and special-purpose IPv4 ranges, including
# shared-address space, documentation, benchmarking, multicast, and reserved IPs.
# Some small globally reachable exceptions are intentionally excluded with their
# containing block. Keep this explicit so Python ipaddress version changes do not
# silently widen the policy. Registry:
# https://www.iana.org/assignments/iana-ipv4-special-registry/
_NONPUBLIC_IPV4 = (
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.0.0.0/24",
    "192.0.2.0/24",
    "192.88.99.0/24",
    "192.168.0.0/16",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "224.0.0.0/4",
    "240.0.0.0/4",
)


def public_ipv4_allowlist() -> list[str]:
    """Return Modal CIDRs that deny nonpublic destinations, including redirects.

    Pass only as outbound_cidr_allowlist, without a domain allowlist: Modal
    combines those policies additively. Omitting IPv6 keeps it denied too.
    Browser loopback CDP stays inside the sandbox rather than using egress.
    """
    allowed = [ip_network("0.0.0.0/0")]
    for value in _NONPUBLIC_IPV4:
        blocked = ip_network(value)
        allowed = [
            part
            for network in allowed
            for part in (
                network.address_exclude(blocked)
                if blocked.subnet_of(network)
                else (network,)
            )
        ]
    return [str(network) for network in sorted(allowed)]


def reference_browser_image():
    """Build the small research runtime without render tools or mounted data."""
    import modal

    return (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install(
            "chromium",
            "ffmpeg",
            "fonts-dejavu-core",
            "fonts-liberation",
            "fonts-noto-core",
            "fonts-noto-cjk",
        )
        # The optional MCP extra requires MCP 2; the coordinator uses MCP 1.
        # Research calls the core harness CLI inside this separate sandbox.
        .pip_install(
            "browser-harness==0.1.13",
            "yt-dlp[default]==2026.8.19",
            "deno==2.7.5",
            "cdp-use==1.4.5",
            "fetch-use==0.4.0",
            "pillow==12.3.0",
            "websockets==15.0.1",
        )
        .env(
            {
                "CHROME_PATH": "/usr/bin/chromium",
                "PYTHONPATH": "/opt/video-use",
                "PYTHONUNBUFFERED": "1",
                "BH_HOME": "/workspace/browser-harness",
                "BH_TELEMETRY": "0",
                "BH_RECORD": "0",
                "BH_TAB_MARKER": "0",
            }
        )
        .run_commands(
            "mkdir -p /workspace/browser-harness && chmod 700 /workspace/browser-harness"
        )
        # Only the trusted stdlib dispatcher belongs in the research sandbox;
        # coordinator, backend, and project/render files are unnecessary here.
        .add_local_file(
            ROOT / "video_use_mcp" / "__init__.py",
            "/opt/video-use/video_use_mcp/__init__.py",
            copy=True,
        )
        .add_local_file(
            ROOT / "video_use_mcp" / "pilot" / "__init__.py",
            "/opt/video-use/video_use_mcp/pilot/__init__.py",
            copy=True,
        )
        .add_local_file(
            ROOT / "video_use_mcp" / "pilot" / "reference_download_worker.py",
            "/opt/video-use/video_use_mcp/pilot/reference_download_worker.py",
            copy=True,
        )
        .add_local_file(
            ROOT / "video_use_mcp" / "pilot" / "reference_browser_worker.py",
            "/opt/video-use/video_use_mcp/pilot/reference_browser_worker.py",
            copy=True,
        )
    )
