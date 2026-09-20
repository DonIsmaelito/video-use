import asyncio

from video_use_mcp import agent
from video_use_mcp.config import Settings
from video_use_mcp.providers import Reply


def test_parallel_finishes_cannot_skip_model_review(tmp_path, monkeypatch):
    class Model:
        def __init__(self, *args):
            self.turn = 0
            self.received_images = False
            self.closed = False

        def user(self, text):
            pass

        async def next(self):
            self.turn += 1
            if self.turn > 1:
                assert self.received_images
            call = {
                "id": "finish",
                "name": "finish",
                "args": {
                    "video_path": "edit/final.mp4",
                    "summary": "Reviewed the encoded frames",
                },
            }
            return Reply(
                "", [call, {**call, "id": "finish-2"}] if self.turn == 1 else [call], 30
            )

        def results(self, results):
            self.received_images = any(value.get("image") for _, value in results)

        async def close(self):
            self.closed = True

    class Sandbox:
        async def safe_path(self, path):
            return "/workspace/" + path

        async def inspect_video(self, path):
            return {"duration": 8, "width": 1920, "height": 1080, "has_audio": False}

        async def run(self, command, timeout):
            return {
                "exit_code": 0,
                "stdout": "video-content-hash  final.mp4"
                if command.startswith("sha256sum")
                else "",
            }

        async def read(self, path):
            return b"encoded-output-contact-sheet"

    monkeypatch.setattr(agent, "AgentModel", Model)
    producer = agent.ProductionAgent(
        Sandbox(),
        {"provider": "openrouter", "model": "test"},
        Settings(tmp_path),
        lambda _: None,
    )
    result = asyncio.run(producer.run("Make a film"))
    assert result["width"] == 1920
    assert producer.model.turn == 2
    assert producer.model.closed
