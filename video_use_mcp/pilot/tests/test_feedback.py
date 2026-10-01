"""Player suggestions belong to an owned media version and change direction once."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.feedback import register_feedback


def fixture():
    values = {
        ("creative", "p"): {
            "revision": 2,
            "choice_revision": 1,
            "brief": "A solar explainer",
            "preferences": "Cream and green",
            "beats": [{"title": "Explain", "seconds": 30}],
        },
        ("progress", "p"): {
            "updates": [{"preview": {"object_id": "video", "duration": 30}}]
        },
    }
    metadata = {}
    store = Mock()
    store.get.side_effect = lambda kind, key: deepcopy(values.get((kind, key)))
    store.put.side_effect = lambda kind, key, value, **kwargs: values.__setitem__(
        (kind, key), deepcopy(value)
    )

    def sql(query, *args):
        if "FROM public.vp_objects" in query:
            if args == ("video", "u", "p"):
                return [{"id": "video", "kind": "video", "name": "preview.mp4"}]
            if args == ("image", "u", "p"):
                return [{"id": "image", "kind": "review", "name": "review.png"}]
            return []
        if "FROM public.vp_revisions" in query:
            return [{"metadata": metadata}] if metadata else []
        return []

    store.sql.side_effect = sql
    config = {}

    def tool(**kwargs):
        config.update(kwargs)
        return lambda fn: fn

    user = Mock(return_value="u")
    call = register_feedback(
        SimpleNamespace(tool=tool), store, user, {"readOnlyHint": False}
    )
    return call, store, values, metadata, config, user


def test_suggestion_is_explicit_app_only_owner_scoped_and_preserves_plan():
    call, store, values, _, config, user = fixture()
    before = deepcopy(values[("creative", "p")])
    result = call("p", "video", 12.3456, "  Make this diagram larger  ", "one")
    user.assert_called_once_with(True)
    store.project.assert_called_once_with("u", "p")
    assert config["meta"]["ui"]["visibility"] == ["app"]
    item = result["feedback"]
    assert item["object_id"] == "video" and item["seconds"] == 12.346
    assert item["note"] == "Make this diagram larger"
    assert result["creative"]["revision"] == 3
    assert result["creative"]["latest_feedback"] == item
    for key in ["brief", "beats", "preferences", "choice_revision"]:
        assert result["creative"][key] == before[key]
    assert values[("feedback", "p")]["items"] == [item]
    assert "scene" not in item  # same project alone cannot identify an encoded scene


def test_exact_retry_is_idempotent_and_changed_retry_is_rejected():
    call, _, values, _, _, _ = fixture()
    first = call("p", "video", 4, "Use larger labels", "same")
    second = call("p", "video", 4, "Use larger labels", "same")
    assert second["repeated"] is True
    assert second["feedback"]["id"] == first["feedback"]["id"]
    assert values[("creative", "p")]["revision"] == 3
    assert len(values[("feedback", "p")]["items"]) == 1
    with pytest.raises(ValueError, match="different suggestion"):
        call("p", "video", 4, "Different", "same")
    assert values[("creative", "p")]["revision"] == 3


@pytest.mark.parametrize(
    "object_id,seconds,note",
    [
        ("other-project-video", 1, "Edit"),
        ("image", 1, "Edit"),
        ("video", -1, "Edit"),
        ("video", float("nan"), "Edit"),
        ("video", float("inf"), "Edit"),
        ("video", 31, "Edit"),
        ("video", 1, ""),
        ("video", 1, "a" * 1201),
    ],
)
def test_wrong_media_invalid_timestamps_and_notes_do_not_change_preferences(
    object_id, seconds, note
):
    call, store, values, _, _, _ = fixture()
    before = deepcopy(values)
    with pytest.raises((ValueError, PermissionError)):
        call("p", object_id, seconds, note, "invalid")
    assert values == before
    store.put.assert_not_called()


@pytest.mark.parametrize("matching", [True, False])
def test_scene_mapping_requires_the_same_encoded_digest(matching):
    call, _, values, metadata, _, _ = fixture()
    metadata.update(duration=30, sha256="encoded-video")
    values[("production_timing", "p")] = {
        "sha256": "encoded-video" if matching else "different-render",
        "scenes": [
            {"title": "Photons", "seconds": 6},
            {"title": "Electricity", "seconds": 24},
        ],
    }
    result = call("p", "video", 7.25, "Slow this down", "scene")
    if matching:
        assert result["feedback"]["scene"] == {
            "index": 1,
            "title": "Electricity",
            "start": 6,
            "end": 30,
        }
    else:
        assert "scene" not in result["feedback"]


def test_feedback_history_is_bounded_without_losing_retry_receipts():
    call, _, values, _, _, _ = fixture()
    first = call("p", "video", 1, "First", "first")
    for index in range(55):
        call("p", "video", 2, f"Edit {index}", f"edit-{index}")
    assert len(values[("feedback", "p")]["items"]) == 50
    revision = values[("creative", "p")]["revision"]
    retry = call("p", "video", 1, "First", "first")
    assert retry["feedback"]["id"] == first["feedback"]["id"]
    assert values[("creative", "p")]["revision"] == revision


def test_retry_after_history_storage_failure_does_not_apply_direction_twice():
    call, store, values, _, _, _ = fixture()
    fail = True

    def put(kind, key, value, **kwargs):
        nonlocal fail
        if kind == "feedback" and fail:
            fail = False
            raise ValueError("storage interrupted after direction saved")
        values[(kind, key)] = deepcopy(value)

    store.put.side_effect = put
    with pytest.raises(ValueError, match="storage interrupted"):
        call("p", "video", 4, "Use larger labels", "retry-after-error")
    assert values[("creative", "p")]["revision"] == 3
    recovered = call("p", "video", 4, "Use larger labels", "retry-after-error")
    assert recovered["repeated"] is True
    assert values[("creative", "p")]["revision"] == 3
    assert len(values[("feedback", "p")]["items"]) == 1
    again = call("p", "video", 4, "Use larger labels", "retry-after-error")
    assert again["feedback"]["id"] == recovered["feedback"]["id"]
    assert values[("creative", "p")]["revision"] == 3
