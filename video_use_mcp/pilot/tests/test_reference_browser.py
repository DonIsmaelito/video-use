"""Reference browser boundaries and real MCP transport without cloud execution."""

import asyncio
import base64
from copy import deepcopy
import hashlib
import io
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

from PIL import Image
import pytest

from video_use_mcp.pilot import reference_sources
from video_use_mcp.pilot.intake import intake_context
from video_use_mcp.pilot.reference_browser import (
    BrowserOperation,
    MAX_IMAGE_BYTES,
    ReferenceBrowserManager,
    prepare_operations,
)
from video_use_mcp.pilot.reference_browser_worker import validate_request
from video_use_mcp.pilot.runtime import require_production_intake
from video_use_mcp.pilot.tests.test_cards import PID, rpc
from video_use_mcp.pilot.tests.test_workflow import call
from video_use_mcp.store import Store

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]

COLLECTION = "https://example.com/collection"
CREATOR = "https://creator.example/film"
EVIDENCE_PATH = "/workspace/reference-evidence/frame.png"


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    path = tmp_path / "reference-sources.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "sources": [
                    {
                        "id": "example",
                        "name": "Example collection",
                        "url": COLLECTION,
                        "categories": ["explainer"],
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(reference_sources, "REGISTRY", path)


def png():
    stream = io.BytesIO()
    Image.new("RGB", (3, 2), "navy").save(stream, format="PNG")
    return stream.getvalue()


def fake_browser(manager, pid=PID):
    """Keep the manager/capture path real, replacing only remote I/O."""
    raw = png()
    manager.store.reserve = Mock(return_value="storage-reservation")
    manager.store.settle = Mock()
    manager.store.upload = Mock()
    manager.store.download = Mock(side_effect=lambda key, path: path.write_bytes(raw))
    sandbox = SimpleNamespace(
        filesystem=SimpleNamespace(
            stat=SimpleNamespace(
                aio=AsyncMock(return_value=SimpleNamespace(size=len(raw)))
            ),
            read_bytes=SimpleNamespace(aio=AsyncMock(return_value=raw)),
        ),
        terminate=SimpleNamespace(aio=AsyncMock()),
    )
    session = {
        "sandbox": sandbox,
        "owner": "tester",
        "links": set(),
        "created": time.time(),
        "touched": time.time(),
        "reservation": "compute-reservation",
    }
    manager.sessions[pid] = session
    manager.session = AsyncMock(return_value=session)
    manager.execute = AsyncMock(
        return_value={"results": [], "evidence": [], "limitations": []}
    )
    return session, raw


@pytest.fixture
def manager(tmp_path, catalog):
    store = Store(tmp_path / "coordinator")
    store.project = Mock(return_value={"title": "Reference research"})
    result = ReferenceBrowserManager(store, SimpleNamespace())
    fake_browser(result)
    return result


def op(action, **kwargs):
    return BrowserOperation(action=action, **kwargs)


def run(manager, request_id="inspect", operations=None, budget=30):
    return asyncio.run(
        manager.run("tester", PID, request_id, operations or [op("read")], budget)
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {"action": "evaluate", "script": "document.cookie"},
        {"action": "read", "script": "document.cookie"},
        {"action": "open", "url": "http://example.com/collection"},
        {"action": "open", "url": "https://127.0.0.1/private"},
        {"action": "open", "url": "https://user:password@example.com/collection"},
        {"action": "open", "url": "https://example.com:8443/collection"},
        {"action": "click"},
        {"action": "fill", "node_id": 0},
        {"action": "press", "key": "Control+L"},
        {"action": "search", "query": "type"},
        {"action": "search", "query": "type", "source_ids": ["a", "b", "c", "d"]},
        {"action": "sample_video", "timestamps": []},
        {"action": "sample_video", "timestamps": [0, 1, 2, 3]},
        {"action": "sample_video", "timestamps": [601]},
        {"action": "sample_video", "timestamps": [float("nan")]},
    ],
)
def test_operation_schema_rejects_unbounded_or_nonpublic_actions(arguments):
    with pytest.raises(ValueError):
        BrowserOperation(**arguments)


def test_prepared_actions_match_worker_contract_without_unused_defaults(catalog):
    actions = [
        op("open", url=COLLECTION, source_id="example"),
        op("read"),
        op("click", node_id=12),
        op("fill", node_id=13, text="kinetic type"),
        op("press"),
        op("scroll"),
        op("screenshot"),
        op("sample_video", timestamps=[0, 3, 600]),
        op("close"),
    ]
    expected = [
        {"action": "open", "url": COLLECTION},
        {"action": "read"},
        {"action": "click", "node_id": 12},
        {"action": "fill", "node_id": 13, "text": "kinetic type"},
        {"action": "press", "key": "Enter"},
        {"action": "scroll", "delta_y": 600},
        {"action": "screenshot"},
        {"action": "sample_video", "timestamps": [0, 3, 600]},
        {"action": "close"},
    ]
    for action, prepared in zip(actions, expected):
        assert prepare_operations([action]) == [prepared]
        assert validate_request({"operations": [prepared]})["operations"] == [prepared]


def test_later_video_can_be_selected_from_snapshot(catalog):
    prepared = prepare_operations([op("sample_video", timestamps=[2], video_index=3)])
    assert prepared == [{"action": "sample_video", "timestamps": [2], "video_index": 3}]
    assert validate_request({"operations": prepared})["operations"] == prepared
    with pytest.raises(ValueError):
        op("sample_video", timestamps=[2], video_index=20)


def test_discovered_media_frames_preserve_source_page(manager):
    media = "https://cdn.example/film.mp4"
    manager.execute.return_value["results"] = [
        {
            "page_url": COLLECTION,
            "links": [],
            "videos": [{"src": media}],
        }
    ]
    run(manager, "discover")
    manager.execute.return_value = {
        "results": [{"page_url": media, "videos": [{"src": media}]}],
        "limitations": [],
        "evidence": [{"path": EVIDENCE_PATH, "kind": "video_frame", "page_url": media}],
    }
    response = deepcopy(manager.execute.return_value)
    manager.execute.side_effect = lambda *args: deepcopy(response)
    result, images = run(
        manager, "sample", [op("open", url=media), op("sample_video", timestamps=[2])]
    )
    assert result["evidence"][0]["source_page_url"] == COLLECTION
    assert result["evidence"][0]["page_url"] == media
    assert images == [png()]
    repeated, _ = run(manager, "sample-again", [op("sample_video", timestamps=[4])])
    assert repeated["evidence"][0]["source_page_url"] == COLLECTION


def test_failed_receipt_write_still_closes_browser(manager):
    original = manager.store.put

    def fail_receipt(kind, key, value, **kwargs):
        if kind == "reference_browser_run" and value["status"] == "failed":
            raise OSError("database unavailable")
        return original(kind, key, value, **kwargs)

    manager.store.put = fail_receipt
    manager.execute.side_effect = ValueError("original browser error")
    sandbox = manager.sessions[PID]["sandbox"]
    with pytest.raises(ValueError, match="original browser error"):
        run(manager)
    sandbox.terminate.aio.assert_awaited_once()
    assert not manager.sessions


def test_search_is_scoped_to_known_sources_and_produces_valid_worker_open(catalog):
    prepared = prepare_operations(
        [op("search", query="lunar typography", source_ids=["example"])]
    )
    url = urlsplit(prepared[0]["url"])
    assert url.hostname == "www.bing.com" and url.path == "/search"
    assert parse_qs(url.query)["q"] == ["lunar typography (site:example.com)"]
    validate_request({"operations": prepared})
    with pytest.raises(ValueError, match="known curated"):
        prepare_operations([op("search", query="moon", source_ids=["invented"])])


def test_open_requires_curated_provenance_or_the_actual_supplied_url(catalog):
    assert prepare_operations([op("open", url=COLLECTION)])
    assert prepare_operations([op("open", url=CREATOR)], discovered_links={CREATOR})
    supplied = op("open", url=CREATOR, user_message="Please use " + CREATOR)
    assert prepare_operations([supplied]) == [{"action": "open", "url": CREATOR}]
    for action in [
        op("open", url=CREATOR),
        op("open", url=CREATOR, user_message="Use another reference"),
        op("open", url="https://example.com/unrelated", source_id="example"),
        op("open", url=CREATOR, source_id="example"),
    ]:
        with pytest.raises(ValueError):
            prepare_operations([action])


@pytest.mark.parametrize(
    "page_url,allowed",
    [
        (COLLECTION + "/film", True),
        ("https://www.bing.com/search?q=moon", False),
        (CREATOR, False),
    ],
)
def test_only_curated_page_links_authorize_creator_navigation(
    manager, page_url, allowed
):
    manager.execute.return_value["results"] = [
        {
            "snapshot": {
                "url": page_url,
                "links": [{"url": CREATOR}, {"url": "https://127.0.0.1"}],
            },
        }
    ]
    run(manager)
    assert (CREATOR in manager.sessions[PID]["links"]) is allowed
    assert "https://127.0.0.1" not in manager.sessions[PID]["links"]
    if allowed:
        run(manager, "creator", [op("open", url=CREATOR)])
        assert manager.execute.await_count == 2
    else:
        with pytest.raises(ValueError, match="curated source"):
            run(manager, "creator", [op("open", url=CREATOR)])
        assert manager.execute.await_count == 1


def test_identical_concurrent_requests_execute_once_and_rehydrate_inline_evidence(
    manager,
):
    manager.execute.return_value["evidence"] = [
        {"path": EVIDENCE_PATH, "kind": "screenshot"}
    ]

    async def scenario():
        return await asyncio.gather(
            *[
                manager.run("tester", PID, "same-request", [op("screenshot")])
                for _ in range(2)
            ]
        )

    first, repeated = asyncio.run(scenario())
    assert first[0]["repeated"] is False and repeated[0]["repeated"] is True
    assert first[0]["evidence"] == repeated[0]["evidence"]
    assert first[1] == repeated[1] == [png()]
    manager.execute.assert_awaited_once()
    manager.store.upload.assert_called_once()
    metadata = first[0]["evidence"][0]
    assert metadata["review_provenance"] == "host_must_inspect"
    assert metadata["capture_provenance"] == "server_acquired"
    assert "path" not in metadata


@pytest.mark.parametrize(
    "operations,budget", [([op("screenshot")], 30), ([op("read")], 31)]
)
def test_request_id_rejects_changed_actions_or_budget(manager, operations, budget):
    run(manager, "same-request")
    with pytest.raises(ValueError, match="different browser actions"):
        run(manager, "same-request", operations, budget)
    manager.execute.assert_awaited_once()


def test_failed_request_is_never_replayed_after_a_possible_side_effect(manager):
    manager.execute.side_effect = TimeoutError("Browser response lost")
    with pytest.raises(TimeoutError):
        run(manager)
    manager.execute.side_effect = None
    with pytest.raises(ValueError, match="new read request"):
        run(manager)
    manager.execute.assert_awaited_once()
    manager.store.settle.assert_called_once()


def test_project_ownership_is_checked_before_completed_retry(manager):
    run(manager)
    manager.store.project.side_effect = PermissionError("Project not found")
    with pytest.raises(PermissionError, match="Project not found"):
        run(manager)
    manager.execute.assert_awaited_once()


@pytest.mark.parametrize(
    "operations,budget,request_id",
    [
        ([], 30, "empty"),
        ([op("read")] * 7, 30, "too-many"),
        ([op("read")], 4, "too-short"),
        ([op("read")], 46, "too-long"),
        ([op("read")], 30, " "),
        ([op("read")], 30, "x" * 121),
        ([op("close"), op("read")], 30, "early-close"),
        ([op("screenshot")] * 5, 30, "too-many-images"),
        (
            [
                op("sample_video", timestamps=[0, 1, 2]),
                op("sample_video", timestamps=[3, 4]),
            ],
            30,
            "too-many-frames",
        ),
    ],
)
def test_invalid_batches_do_not_start_or_execute_browser(
    manager, operations, budget, request_id
):
    with pytest.raises(ValueError):
        asyncio.run(manager.run("tester", PID, request_id, operations, budget))
    manager.session.assert_not_awaited()
    manager.execute.assert_not_awaited()
    manager.store.reserve.assert_not_called()


def test_excess_worker_images_are_rejected_before_capture_storage(manager):
    manager.execute.return_value["evidence"] = [{"path": EVIDENCE_PATH}] * 5
    with pytest.raises(ValueError, match="at most four images"):
        run(manager)
    manager.store.upload.assert_not_called()
    manager.store.reserve.assert_not_called()


@pytest.mark.parametrize(
    "path",
    [
        "/workspace/sources/secret.png",
        "/tmp/frame.png",
        "/workspace/reference-evidence/frame.jpg",
    ],
)
def test_capture_never_reads_paths_outside_its_png_evidence_directory(manager, path):
    sandbox = manager.sessions[PID]["sandbox"]
    with pytest.raises(ValueError, match="Invalid browser evidence path"):
        asyncio.run(manager.capture("tester", PID, sandbox, {"path": path}))
    sandbox.filesystem.stat.aio.assert_not_awaited()
    manager.store.upload.assert_not_called()


@pytest.mark.parametrize(
    "reported_size,raw", [(MAX_IMAGE_BYTES + 1, b""), (1, b"x" * (MAX_IMAGE_BYTES + 1))]
)
def test_capture_enforces_image_limit_on_stat_and_actual_bytes(
    manager, reported_size, raw
):
    sandbox = manager.sessions[PID]["sandbox"]
    sandbox.filesystem.stat.aio.return_value.size = reported_size
    sandbox.filesystem.read_bytes.aio.return_value = raw
    with pytest.raises(ValueError, match="image limit"):
        asyncio.run(manager.capture("tester", PID, sandbox, {"path": EVIDENCE_PATH}))
    manager.store.upload.assert_not_called()


def store_evidence(manager, *, owner="tester", project=PID, raw=None):
    data = png() if raw is None else raw
    manager.store.put(
        "reference_browser_evidence",
        "capture-id",
        {
            "owner": owner,
            "project": project,
            "key": "private/reference.png",
            "evidence_id": "capture-id",
            "sha256": hashlib.sha256(data).hexdigest(),
            "review_provenance": "host_must_inspect",
        },
    )


@pytest.mark.parametrize(
    "owner,project", [("someone-else", PID), ("tester", "other-project")]
)
def test_evidence_cannot_cross_owner_or_project(manager, owner, project):
    store_evidence(manager, owner=owner, project=project)
    with pytest.raises(PermissionError, match="not found"):
        asyncio.run(manager.evidence("tester", PID, "capture-id"))
    manager.store.project.assert_called_once_with("tester", PID)
    manager.store.download.assert_not_called()


def test_evidence_retrieval_checks_hash_and_hides_storage_fields(manager):
    store_evidence(manager)
    metadata, raw = asyncio.run(manager.evidence("tester", PID, "capture-id"))
    assert raw == png()
    assert not {"owner", "project", "key"}.intersection(metadata)
    manager.store.download.side_effect = lambda key, path: path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        asyncio.run(manager.evidence("tester", PID, "capture-id"))


def test_evidence_retrieval_rejects_oversized_download(manager):
    store_evidence(manager)
    manager.store.download.side_effect = lambda key, path: path.write_bytes(
        b"x" * (MAX_IMAGE_BYTES + 1)
    )
    with pytest.raises(ValueError, match="image limit"):
        asyncio.run(manager.evidence("tester", PID, "capture-id"))


def test_close_alone_does_not_allocate_browser(manager):
    result, images = run(manager, operations=[op("close")])
    assert result["results"] == [{"action": "close", "ok": True}] and images == []
    manager.session.assert_not_awaited()
    manager.execute.assert_not_awaited()
    assert PID not in manager.sessions


def test_mcp_reference_intake_returns_real_images_without_rendering_or_approval(
    pilot, catalog
):
    _, app = pilot
    started = call(
        pilot,
        "start_video",
        {
            "title": "Moon",
            "brief": "Explain lunar phases",
            "category": "explainer",
            "output_profile": {
                "duration_seconds": 30,
                "viewing_destination": "YouTube",
            },
        },
    )
    pid = started["project_id"]
    call(
        pilot,
        "record_video_answers",
        started["question"]["record_with"]["arguments"]
        | {
            "request_id": "mode",
            "user_message": "Hands on",
            "answers": {"involvement": "hands_on"},
        },
    )
    before = deepcopy(app.state.store.get("creative", pid))
    assert intake_context(before)["phase"] == "references"
    with pytest.raises(ValueError):
        require_production_intake(before, "step", {"production_stage": "excerpt"})
    app.state.manager.submit = Mock(
        side_effect=AssertionError("Reference browsing must not render")
    )
    manager = app.state.reference_manager
    _, raw = fake_browser(manager, pid)
    manager.execute.return_value = {
        "results": [
            {"snapshot": {"url": COLLECTION, "text": "Moon film", "links": []}}
        ],
        "evidence": [
            {
                "path": EVIDENCE_PATH,
                "kind": "video_sample",
                "requested_seconds": 2,
                "actual_seconds": 2,
            }
        ],
        "limitations": ["Sampled stills do not establish continuous motion or audio"],
    }
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "browse_video_references",
            "arguments": {
                "project_id": pid,
                "request_id": "reference-sample",
                "operations": [
                    {"action": "open", "url": COLLECTION, "source_id": "example"},
                    {"action": "sample_video", "timestamps": [2]},
                ],
            },
        },
    )
    assert not result.get("isError"), result
    data = result["structuredContent"]
    assert json.loads(result["content"][0]["text"]) == data
    images = [item for item in result["content"] if item["type"] == "image"]
    assert len(images) == 1 and base64.b64decode(images[0]["data"]) == raw
    assert images[0]["mimeType"] == "image/png"
    assert data["engine"] == "browser-harness" and data["model_api_cost_usd"] == 0
    assert "continuous motion" in data["limitations"][0]
    assert "ui" not in result.get("_meta", {})
    validate_request(manager.execute.await_args.args[1])
    assert app.state.store.get("creative", pid) == before
    app.state.manager.submit.assert_not_called()

    retained = rpc(
        pilot,
        "tools/call",
        {
            "name": "read_video_reference_evidence",
            "arguments": {
                "project_id": pid,
                "evidence_id": data["evidence"][0]["evidence_id"],
            },
        },
    )
    assert not retained.get("isError"), retained
    assert base64.b64decode(retained["content"][1]["data"]) == raw
    assert retained["structuredContent"]["review_provenance"] == "host_must_inspect"
    manager.execute.assert_awaited_once()


def test_mcp_evidence_read_denies_another_project_without_downloading(pilot, catalog):
    manager = pilot[1].state.reference_manager
    fake_browser(manager)
    store_evidence(manager, project="another-project")
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "read_video_reference_evidence",
            "arguments": {
                "project_id": PID,
                "evidence_id": "capture-id",
            },
        },
    )
    assert result.get("isError"), result
    manager.store.download.assert_not_called()
    manager.execute.assert_not_awaited()
