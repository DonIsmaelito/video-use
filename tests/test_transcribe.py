import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import transcribe


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "interview.mp4"
        self.video.write_bytes(b"source one")
        self.edit = self.root / "edit"
        self.payload = {"text": "Um, hello.", "words": [
            {"text": "Um,", "start": 0.1, "end": 0.4,
             "speaker_id": "speaker_0", "type": "word"}]}

    def produce(self, **kwargs):
        with patch.object(transcribe, "extract_audio", side_effect=lambda _v, out: out.write_bytes(b"wav")), \
             patch.object(transcribe, "call_scribe", return_value=json.loads(json.dumps(self.payload))):
            return transcribe.transcribe_one(self.video, self.edit, "test-key", verbose=False, **kwargs)

    def test_identical_source_and_parameters_reuse_without_network(self):
        output = self.produce(language="en", num_speakers=2)
        recorded = json.loads(output.read_text())
        self.assertEqual(recorded["words"], self.payload["words"])
        self.assertEqual(recorded["_video_use"]["model_id"], "scribe_v2")
        with patch.object(transcribe, "call_scribe") as remote, patch.object(transcribe, "extract_audio") as extract:
            again = transcribe.transcribe_one(self.video, self.edit, "", language="en", num_speakers=2, verbose=False)
        self.assertEqual(output, again)
        remote.assert_not_called()
        extract.assert_not_called()

    def test_changed_source_same_name_cannot_reuse_or_overwrite_transcript(self):
        output = self.produce()
        original = output.read_bytes()
        self.video.write_bytes(b"different interview")
        with patch.object(transcribe, "call_scribe") as remote, self.assertRaisesRegex(ValueError, "source bytes"):
            transcribe.transcribe_one(self.video, self.edit, "", verbose=False)
        self.assertEqual(output.read_bytes(), original)
        remote.assert_not_called()

    def test_changed_settings_cannot_mislabel_cached_words(self):
        output = self.produce()
        original = output.read_bytes()
        for options in [{"language": "fr"}, {"num_speakers": 2}, {"model": "scribe_v1"}]:
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, "settings"):
                transcribe.cached_transcript(self.video, self.edit, **options)
        self.assertEqual(original, output.read_bytes())

    def test_legacy_or_malformed_cache_is_preserved(self):
        folder = self.edit / "transcripts"
        folder.mkdir(parents=True)
        output = folder / "interview.json"
        for content in [json.dumps(self.payload), "not json", "[]"]:
            output.write_text(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                transcribe.cached_transcript(self.video, self.edit)
            self.assertEqual(content, output.read_text())

    def test_source_mutation_during_request_prevents_install(self):
        def answer(*_):
            self.video.write_bytes(b"changed while uploading")
            return self.payload
        with patch.object(transcribe, "extract_audio", side_effect=lambda _v, out: out.write_bytes(b"wav")), \
             patch.object(transcribe, "call_scribe", side_effect=answer), \
             self.assertRaisesRegex(ValueError, "Source changed"):
            transcribe.transcribe_one(self.video, self.edit, "test-key", verbose=False)
        self.assertFalse((self.edit / "transcripts/interview.json").exists())

    def test_competing_writer_is_not_overwritten(self):
        output = self.edit / "transcripts/interview.json"
        def answer(*_):
            output.write_text("another writer")
            return self.payload
        with patch.object(transcribe, "extract_audio", side_effect=lambda _v, out: out.write_bytes(b"wav")), \
             patch.object(transcribe, "call_scribe", side_effect=answer), self.assertRaises(FileExistsError):
            transcribe.transcribe_one(self.video, self.edit, "test-key", verbose=False)
        self.assertEqual(output.read_text(), "another writer")
        self.assertEqual(list(output.parent.glob("*.tmp")), [])

    def test_scribe_v2_request_retains_word_timing_and_diarization(self):
        audio = self.root / "audio.wav"
        audio.write_bytes(b"wav")
        response = SimpleNamespace(status_code=200, json=lambda: self.payload)
        with patch.object(transcribe.requests, "post", return_value=response) as post:
            result = transcribe.call_scribe(audio, "test-key", "en", 2)
        self.assertEqual(result, self.payload)
        self.assertEqual(post.call_args.kwargs["data"], {
            "model_id": "scribe_v2", "diarize": "true", "tag_audio_events": "true",
            "timestamps_granularity": "word", "language_code": "en", "num_speakers": "2"})

    def test_provider_error_body_is_not_echoed(self):
        audio = self.root / "audio.wav"
        audio.write_bytes(b"wav")
        response = SimpleNamespace(status_code=401, text="private upstream diagnostics")
        with patch.object(transcribe.requests, "post", return_value=response), self.assertRaises(RuntimeError) as error:
            transcribe.call_scribe(audio, "test-key")
        self.assertEqual(str(error.exception), "Scribe returned HTTP 401")

    def test_invalid_speaker_counts_rejected_before_request(self):
        for count in [True, 0, -1, 33, 2.5, "2"]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                transcribe.source_identity(self.video, "en", count, "scribe_v2")

    def test_environment_key_takes_precedence(self):
        with patch.dict(transcribe.os.environ, {"ELEVENLABS_API_KEY": "test-environment-value"}), \
             patch.object(transcribe, "dotenv_values") as read:
            self.assertEqual(transcribe.load_api_key(), "test-environment-value")
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
