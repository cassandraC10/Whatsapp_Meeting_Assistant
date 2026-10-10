import os
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

# The test stubs the Gemini SDK because the production SDK is not installed
# in the lightweight local test environment. No network/model call is made.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-a-real-secret")
google_module = types.ModuleType("google")
google_module.__path__ = []
genai_module = types.ModuleType("google.genai")
class FakeClient:
    def __init__(self, **kwargs):
        self.models = types.SimpleNamespace()
genai_module.Client = FakeClient
google_module.genai = genai_module
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.genai", genai_module)

from transcription import transcriber


def main():
    with TemporaryDirectory() as temporary:
        directory = Path(temporary)
        (directory / "mic_raw.webm").write_bytes(b"fake-audio")
        with patch.object(transcriber, "transcribe_audio", return_value="We agreed to follow up Monday.") as mocked:
            result = transcriber.transcribe_call(directory, call_title="Mobile microphone-only test")
        assert result["my_transcript"] == "We agreed to follow up Monday."
        assert result["their_transcript"] == ""
        assert "follow up Monday" in result["combined_transcript"]
        assert mocked.call_count == 1
    print("Microphone-only transcription smoke test: PASS")


if __name__ == "__main__":
    main()
