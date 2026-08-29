import threading
from pathlib import Path

from audio.recorder import MeetingRecorder


class RecorderManager:
    """
    Keeps active recorder instances by call ID.
    """

    def __init__(self):
        self._recorders: dict[
            str,
            MeetingRecorder,
        ] = {}

        self._lock = threading.Lock()

    def start(
        self,
        call_id: str,
        output_directory: str | Path,
    ) -> MeetingRecorder:
        with self._lock:
            if call_id in self._recorders:
                raise RuntimeError(
                    "This call already has "
                    "an active recorder."
                )

            recorder = MeetingRecorder(
                output_directory=output_directory
            )

            self._recorders[
                call_id
            ] = recorder

        try:
            recorder.start()

        except Exception:
            with self._lock:
                self._recorders.pop(
                    call_id,
                    None,
                )

            raise

        return recorder

    def pause(
        self,
        call_id: str,
    ) -> None:
        recorder = self._require_recorder(
            call_id
        )

        recorder.pause()

    def resume(
        self,
        call_id: str,
    ) -> None:
        recorder = self._require_recorder(
            call_id
        )

        recorder.resume()

    def finish(
        self,
        call_id: str,
    ) -> dict:
        recorder = self._require_recorder(
            call_id
        )

        result = recorder.stop()

        # Only remove it after stop + save succeeded.
        with self._lock:
            self._recorders.pop(
                call_id,
                None,
            )

        return result

    def is_recording(
        self,
        call_id: str,
    ) -> bool:
        with self._lock:
            recorder = self._recorders.get(
                call_id
            )

        return bool(
            recorder
            and recorder.is_recording
        )

    def is_paused(
        self,
        call_id: str,
    ) -> bool:
        with self._lock:
            recorder = self._recorders.get(
                call_id
            )

        return bool(
            recorder
            and recorder.is_paused
        )

    def elapsed_seconds(
        self,
        call_id: str,
    ) -> int:
        with self._lock:
            recorder = self._recorders.get(
                call_id
            )

        if recorder is None:
            return 0

        return recorder.elapsed_seconds()

    def has_active_recording(
        self,
    ) -> bool:
        with self._lock:
            return bool(
                self._recorders
            )

    def _require_recorder(
        self,
        call_id: str,
    ) -> MeetingRecorder:
        with self._lock:
            recorder = self._recorders.get(
                call_id
            )

        if recorder is None:
            raise RuntimeError(
                "No active recording exists "
                "for this call."
            )

        return recorder