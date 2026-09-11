import copy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "openscreen_interactions", Path(__file__).parents[1] / "helpers" / "openscreen_interactions.py"
)
interactions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(interactions)


def sample(time_s, kind="move", cx=0.5, cy=0.5):
    return {"timeMs": time_s * 1000, "cx": cx, "cy": cy, "interactionType": kind}


class InteractionZoomTests(unittest.TestCase):
    def test_hover_and_unknown_scroll_events_do_not_invent_clicks(self):
        result = interactions.interaction_zooms({"samples": [sample(0), sample(4), sample(8, "scroll")]}, 20)
        self.assertEqual(result["zoom_regions"], [])
        self.assertEqual(result["summary"]["source_clicks"], 0)
        self.assertEqual(result["summary"]["ignored_event_types"], {"scroll": 1})

    def test_observed_click_sets_native_timing_and_cursor_follow(self):
        sidecar = {"samples": [sample(0), sample(4, "click", 0.3, 0.7), sample(4.1, "mouseup", 0.3, 0.7)]}
        result = interactions.interaction_zooms(sidecar, 20, depth=2)
        region = result["zoom_regions"][0]
        self.assertEqual((region["startMs"], region["endMs"]), (3500, 5000))
        self.assertEqual(region["focusMode"], "auto")
        self.assertEqual(region["focus"], {"cx": 0.3, "cy": 0.7})
        self.assertEqual(region["depth"], 2)
        self.assertEqual(result["summary"]["covered_interactions"], 1)
        self.assertEqual(result["summary"]["source_drags"], 0)

    def test_real_drag_follows_during_motion_then_returns(self):
        sidecar = {"samples": [sample(4, "click", 0.2), sample(5, cx=0.4),
                               sample(7, cx=0.7), sample(8, "mouseup", 0.8)]}
        result = interactions.interaction_zooms(sidecar, 20)
        self.assertEqual(result["summary"]["source_clicks"], 1)
        self.assertEqual(result["summary"]["source_drags"], 1)
        self.assertEqual(result["summary"]["covered_interactions"], 1)
        self.assertEqual(result["zoom_regions"][0]["endMs"], 8350)
        self.assertEqual(result["zoom_regions"][0]["focusMode"], "auto")

    def test_fractional_capture_milliseconds_do_not_lose_click_coverage(self):
        result = interactions.interaction_zooms({"samples": [sample(4.0004, "click")]}, 20)
        self.assertEqual(result["zoom_regions"][0]["startMs"], 3501)
        self.assertEqual(result["summary"]["covered_interactions"], 1)

    def test_drag_can_resume_after_required_overview_with_partial_coverage(self):
        samples = [sample(4, "click"), sample(4.1, "mouseup"), sample(6, "click", 0.2),
                   sample(8, cx=0.5), sample(10, "mouseup", 0.8)]
        result = interactions.interaction_zooms({"samples": samples}, 20)
        self.assertEqual(len(result["zoom_regions"]), 2)
        self.assertEqual(result["summary"]["covered_interactions"], 1)
        self.assertEqual(result["summary"]["partially_covered_interactions"], 1)
        earlier, later = result["zoom_regions"]
        first_end = earlier["endMs"] / 1000 + interactions.ZOOM_OUT_S
        next_start = (later["startMs"] + 500) / 1000 - interactions.ZOOM_IN_S
        self.assertGreaterEqual(next_start - first_end, 2)

    def test_long_drag_is_bounded_and_partial_coverage_reported(self):
        result = interactions.interaction_zooms({"samples": [sample(4, "click", 0.2),
                                               sample(12, cx=0.5), sample(25, "mouseup", 0.8)]}, 30)
        self.assertEqual(result["zoom_regions"][0]["endMs"], 14000)
        self.assertEqual(result["summary"]["partially_covered_interactions"], 1)
        coverage = result["summary"]["interactions"][0]
        self.assertEqual(coverage["covered_spans"][0]["end_s"], 14)
        self.assertEqual(coverage["end_s"], 25)

    def test_close_clicks_cluster_without_a_long_idle_hold(self):
        result = interactions.interaction_zooms({"samples": [sample(4, "click"), sample(4.1, "mouseup"),
                                               sample(5, "click"), sample(5.1, "mouseup")]}, 20)
        self.assertEqual(len(result["zoom_regions"]), 1)
        self.assertEqual(result["zoom_regions"][0]["endMs"], 6000)
        self.assertEqual(result["summary"]["covered_interactions"], 2)

    def test_dense_clicks_keep_bounded_holds_and_honest_omissions(self):
        samples = [s for t in range(4, 23) for s in (sample(t, "click"), sample(t + 0.1, "mouseup"))]
        result = interactions.interaction_zooms({"samples": samples}, 30)
        regions = result["zoom_regions"]
        self.assertGreater(result["summary"]["omitted_interactions"], 0)
        for region in regions:
            self.assertLessEqual(region["endMs"] / 1000 - (region["startMs"] + 500) / 1000, 3)
        for previous, current in zip(regions, regions[1:]):
            prior_end = previous["endMs"] / 1000 + interactions.ZOOM_OUT_S
            next_start = (current["startMs"] + 500) / 1000 - interactions.ZOOM_IN_S
            self.assertGreaterEqual(next_start - prior_end, 2)

    def test_early_and_late_clicks_leave_overview_and_are_reported(self):
        result = interactions.interaction_zooms({"samples": [sample(0.5, "click"), sample(0.6, "mouseup"),
                                               sample(19, "click"), sample(19.1, "mouseup")]}, 20)
        self.assertEqual(result["zoom_regions"], [])
        self.assertEqual(result["summary"]["omitted_interactions"], 2)

    def test_unpaired_down_is_not_claimed_as_a_drag(self):
        result = interactions.interaction_zooms({"samples": [sample(4, "click", 0.1), sample(10, cx=0.9)]}, 20)
        self.assertEqual(result["summary"]["source_drags"], 0)
        self.assertEqual(result["summary"]["unmatched_downs"], 1)
        self.assertEqual(result["zoom_regions"][0]["endMs"], 5000)

    def test_unknown_fields_are_preserved_and_input_not_mutated(self):
        sidecar = {"captureId": "real-recording", "samples": [{**sample(4, "click"), "cursorType": "pointer"}]}
        before = copy.deepcopy(sidecar)
        interactions.interaction_zooms(sidecar, 20)
        self.assertEqual(sidecar, before)

    def test_small_end_tolerance_is_reported(self):
        result = interactions.interaction_zooms({"samples": [sample(0), sample(20.025)]}, 20)
        self.assertEqual(result["summary"]["clamped_end_samples"], 1)

    def test_malformed_timing_coordinates_and_empty_samples_fail(self):
        cases = [[], [sample(-1)], [sample(4), sample(3)], [sample(20.1)],
                 [sample(float("nan"))], [sample(4, cx=float("inf"))],
                 [sample(4, cx=-0.1)], [sample(4, cy=1.1)],
                 [{"timeMs": 4000, "cy": 0.5}], ["not a point"]]
        for samples in cases:
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                interactions.interaction_zooms({"samples": samples}, 20)
        for depth in (True, 0, 7, 1.5):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                interactions.interaction_zooms({"samples": [sample(0)]}, 20, depth)


if __name__ == "__main__":
    unittest.main()
