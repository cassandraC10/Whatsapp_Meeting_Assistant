import threading
from pathlib import Path

from audio.recorder import MeetingRecorder


class RecorderManager:
    """
    Keeps track of active recorder instances.

    A recorder belongs to exactly one call ID.
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
                    "This call is already recording."
                )

            recorder = MeetingRecorder(
                output_directory=output_directory
            )

            recorder.start()

            self._recorders[
                call_id
            ] = recorder

            return recorder

    def finish(
        self,
        call_id: str,
    ) -> dict:
        with self._lock:
            recorder = self._recorders.get(
                call_id
            )

        if recorder is None:
            raise RuntimeError(
                "No active recording exists "
                "for this call."
            )

        try:
            result = recorder.stop()

            return result

        finally:
            with self._lock:
                self._recorders.pop(
                    call_id,
                    None,
                )

    def is_recording(
        self,
        call_id: str,
    ) -> bool:
        with self._lock:
            recorder = self._recorders.get(
                call_id
            )

            if recorder is None:
                return False

            return recorder.is_recording

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