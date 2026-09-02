import json
import tempfile
import unittest
from pathlib import Path

from helpers import captions


class LoadWordsTests(unittest.TestCase):
    def test_reads_elevenlabs_character_alignment(self):
        payload = {
            "alignment": {
                "characters": list("Hi there."),
                "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
                "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
            }
        }
        words = captions.load_words(payload)
        self.assertEqual([w["text"] for w in words], ["Hi", "there."])
        self.assertEqual(words[0]["start"], 0.0)
        self.assertEqual(words[1]["end"], 0.9)

    def test_reads_generic_word_list(self):
        words = captions.load_words({"words": [{"word": "Go", "start": 1.0, "end": 1.2}]})
        self.assertEqual(words, [{"text": "Go", "start": 1.0, "end": 1.2}])

    def test_rejects_payload_without_timing(self):
        with self.assertRaises(ValueError):
            captions.load_words({"text": "no timestamps"})


class ChunkWordsTests(unittest.TestCase):
    def test_breaks_on_punctuation_and_max_words(self):
        words = [
            {"text": t, "start": i * 0.5, "end": i * 0.5 + 0.4}
            for i, t in enumerate(["We", "fixed", "this.", "Now", "it", "works", "fast", "again"])
        ]
        cues = captions.chunk_words(words, max_words=3, max_characters=44)
        self.assertEqual([c[2] for c in cues], ["We fixed this.", "Now it works", "fast again"])
        self.assertEqual(cues[0][0], 0.0)
        self.assertAlmostEqual(cues[0][1], 1.4)


class WriteAssTests(unittest.TestCase):
    def test_writes_caption_style_and_wrapped_dialogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "master.ass"
            captions.write_ass(
                [(0.0, 1.5, "Short cue"), (2.0, 4.0, "This cue is long enough that it wraps twice")],
                out,
                width=1920,
                height=1080,
            )
            text = out.read_text()
        self.assertIn("PlayResX: 1920", text)
        self.assertIn("Style: Caption,Helvetica,42", text)
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:01.50,Caption,,0,0,0,,Short cue", text)
        self.assertIn("\\N", text.splitlines()[-1])

    def test_rejects_safe_rail_outside_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                captions.write_ass([], Path(tmp) / "x.ass", safe_bottom=0.5)


if __name__ == "__main__":
    unittest.main()
