import threading
import time
from math import gcd
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
import sounddevice as sd
from scipy.io.wavfile import write
from scipy.signal import resample_poly


TARGET_SAMPLE_RATE = 44100
MIC_CHANNELS = 1
BLOCK_SIZE = 1024

NORMAL_STOP_TIMEOUT = 5
FORCED_STOP_TIMEOUT = 3


class MeetingRecorder:
    """
    Records the local microphone and Windows system audio separately.

    Output files:
        mic_raw.wav
        system_raw.wav
        meeting.wav

    Each recorder instance writes to its own output directory.
    """

    def __init__(
        self,
        output_directory: str | Path | None = None,
        mic_device_id: int | None = 1,
    ):
        self.output_directory = Path(
            output_directory or Path.cwd()
        )

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.mic_device_id = mic_device_id

        self.mic_file = (
            self.output_directory / "mic_raw.wav"
        )

        self.system_file = (
            self.output_directory / "system_raw.wav"
        )

        self.mixed_file = (
            self.output_directory / "meeting.wav"
        )

        self.stop_event = threading.Event()

        self.results: dict = {}

        self.mic_thread: threading.Thread | None = None
        self.system_thread: threading.Thread | None = None

        self.is_recording = False
        self.started_at: float | None = None

    def start(self) -> None:
        if self.is_recording:
            raise RuntimeError(
                "Recording is already running."
            )

        self.results = {}
        self.stop_event.clear()

        self.started_at = time.time()
        self.is_recording = True

        self.mic_thread = threading.Thread(
            target=self._record_microphone,
            daemon=True,
            name="TCA-MicrophoneRecorder",
        )

        self.system_thread = threading.Thread(
            target=self._record_system_audio,
            daemon=True,
            name="TCA-SystemAudioRecorder",
        )

        print(
            f"Starting recording in: "
            f"{self.output_directory}"
        )

        try:
            self.mic_thread.start()
            self.system_thread.start()

        except Exception:
            self.is_recording = False
            self.stop_event.set()
            raise

    def stop(self) -> dict:
        if not self.is_recording:
            raise RuntimeError(
                "No recording is currently running."
            )

        print("Stopping meeting recording...")

        self.stop_event.set()

        self._wait_for_threads()

        self.is_recording = False

        self._check_errors()

        mic_audio = self.results["mic"]

        system_audio = self.results["system"]

        system_rate = self.results[
            "system_sample_rate"
        ]

        mic_audio = mic_audio.astype(
            np.float32
        )

        system_audio = self._resample_audio(
            system_audio,
            system_rate,
            TARGET_SAMPLE_RATE,
        )

        minimum_length = min(
            len(mic_audio),
            len(system_audio),
        )

        if minimum_length <= 0:
            raise RuntimeError(
                "Recording contains no usable audio."
            )

        mic_audio = mic_audio[
            :minimum_length
        ]

        system_audio = system_audio[
            :minimum_length
        ]

        self._save_recordings(
            mic_audio,
            system_audio,
        )

        duration = (
            minimum_length
            / TARGET_SAMPLE_RATE
        )

        print(
            f"Recording saved. "
            f"Duration: {duration:.2f} seconds."
        )

        return {
            "mic": str(self.mic_file),
            "system": str(self.system_file),
            "mixed": str(self.mixed_file),
            "duration": duration,
        }

    def elapsed_seconds(self) -> int:
        if (
            not self.is_recording
            or self.started_at is None
        ):
            return 0

        return int(
            time.time() - self.started_at
        )

    def _wait_for_threads(self) -> None:
        if self.mic_thread is None:
            raise RuntimeError(
                "Microphone thread was not created."
            )

        if self.system_thread is None:
            raise RuntimeError(
                "System audio thread was not created."
            )

        print(
            "Waiting for microphone thread..."
        )

        self.mic_thread.join(
            timeout=NORMAL_STOP_TIMEOUT
        )

        print(
            "Microphone alive after stop:",
            self.mic_thread.is_alive(),
        )

        print(
            "Waiting for system audio thread..."
        )

        self.system_thread.join(
            timeout=NORMAL_STOP_TIMEOUT
        )

        print(
            "System audio alive after stop:",
            self.system_thread.is_alive(),
        )

        if self.mic_thread.is_alive():
            self.mic_thread.join(
                timeout=FORCED_STOP_TIMEOUT
            )

        if self.system_thread.is_alive():
            self.system_thread.join(
                timeout=FORCED_STOP_TIMEOUT
            )

        if self.mic_thread.is_alive():
            raise RuntimeError(
                "Microphone recorder did not stop cleanly."
            )

        if self.system_thread.is_alive():
            raise RuntimeError(
                "System audio recorder did not stop cleanly."
            )

    def _record_microphone(self) -> None:
        frames = []

        try:
            print(
                "Microphone recording thread started."
            )

            with sd.InputStream(
                samplerate=TARGET_SAMPLE_RATE,
                channels=MIC_CHANNELS,
                dtype="int16",
                device=self.mic_device_id,
                blocksize=BLOCK_SIZE,
            ) as stream:
                while not self.stop_event.is_set():
                    data, overflowed = stream.read(
                        BLOCK_SIZE
                    )

                    if overflowed:
                        print(
                            "Warning: microphone "
                            "buffer overflow."
                        )

                    frames.append(
                        data.copy()
                    )

            if not frames:
                raise RuntimeError(
                    "No microphone audio was captured."
                )

            audio = np.concatenate(
                frames,
                axis=0,
            )

            self.results["mic"] = (
                audio.flatten()
            )

            self.results[
                "mic_sample_rate"
            ] = TARGET_SAMPLE_RATE

            print(
                "Microphone recording thread stopped."
            )

        except Exception as error:
            self.results[
                "mic_error"
            ] = error

            print(
                "Microphone recording error:",
                error,
            )

    def _find_loopback_device(
        self,
        p: pyaudio.PyAudio,
    ) -> dict:
        wasapi_info = (
            p.get_host_api_info_by_type(
                pyaudio.paWASAPI
            )
        )

        output_index = wasapi_info[
            "defaultOutputDevice"
        ]

        output_device = (
            p.get_device_info_by_index(
                output_index
            )
        )

        print(
            "Default Windows output:",
            output_device["name"],
        )

        if output_device.get(
            "isLoopbackDevice",
            False,
        ):
            return output_device

        for loopback_device in (
            p.get_loopback_device_info_generator()
        ):
            if (
                output_device["name"]
                in loopback_device["name"]
            ):
                print(
                    "Using WASAPI loopback:",
                    loopback_device["name"],
                )

                return loopback_device

        raise RuntimeError(
            "Could not find the WASAPI loopback "
            "device for the default Windows output."
        )

    def _record_system_audio(self) -> None:
        p = pyaudio.PyAudio()

        stream = None
        frames = []

        try:
            print(
                "System audio recording thread started."
            )

            device = self._find_loopback_device(
                p
            )

            sample_rate = int(
                device["defaultSampleRate"]
            )

            channels = int(
                device["maxInputChannels"]
            )

            if channels <= 0:
                raise RuntimeError(
                    "Loopback device has no "
                    "available input channels."
                )

            print(
                "System sample rate:",
                sample_rate,
            )

            print(
                "System channels:",
                channels,
            )

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=BLOCK_SIZE,
            )

            while not self.stop_event.is_set():
                data = stream.read(
                    BLOCK_SIZE,
                    exception_on_overflow=False,
                )

                frames.append(data)

            if not frames:
                raise RuntimeError(
                    "No system audio was captured."
                )

            raw_audio = np.frombuffer(
                b"".join(frames),
                dtype=np.int16,
            )

            if channels > 1:
                usable_length = (
                    len(raw_audio)
                    // channels
                    * channels
                )

                raw_audio = raw_audio[
                    :usable_length
                ]

                raw_audio = raw_audio.reshape(
                    -1,
                    channels,
                )

                raw_audio = (
                    raw_audio
                    .mean(axis=1)
                    .astype(np.int16)
                )

            self.results[
                "system"
            ] = raw_audio

            self.results[
                "system_sample_rate"
            ] = sample_rate

            print(
                "System audio recording thread stopped."
            )

        except Exception as error:
            self.results[
                "system_error"
            ] = error

            print(
                "System audio recording error:",
                error,
            )

        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                except Exception:
                    pass

                try:
                    stream.close()
                except Exception:
                    pass

            p.terminate()

    def _check_errors(self) -> None:
        if "mic_error" in self.results:
            raise RuntimeError(
                "Microphone recording failed: "
                f"{self.results['mic_error']}"
            )

        if "system_error" in self.results:
            raise RuntimeError(
                "System audio recording failed: "
                f"{self.results['system_error']}"
            )

        if "mic" not in self.results:
            raise RuntimeError(
                "Microphone produced no audio."
            )

        if "system" not in self.results:
            raise RuntimeError(
                "System audio produced no audio."
            )

    @staticmethod
    def _resample_audio(
        audio: np.ndarray,
        original_rate: int,
        target_rate: int,
    ) -> np.ndarray:
        original_rate = int(original_rate)
        target_rate = int(target_rate)

        if original_rate == target_rate:
            return audio.astype(
                np.float32
            )

        common_divisor = gcd(
            original_rate,
            target_rate,
        )

        up = (
            target_rate
            // common_divisor
        )

        down = (
            original_rate
            // common_divisor
        )

        return resample_poly(
            audio.astype(np.float32),
            up,
            down,
        ).astype(np.float32)

    @staticmethod
    def _normalize_audio(
        audio: np.ndarray,
    ) -> np.ndarray:
        audio = audio.astype(
            np.float32
        )

        if len(audio) == 0:
            return audio

        peak = np.max(
            np.abs(audio)
        )

        if peak == 0:
            return audio

        return audio / peak

    def _mix_audio(
        self,
        mic_audio: np.ndarray,
        system_audio: np.ndarray,
    ) -> np.ndarray:
        length = min(
            len(mic_audio),
            len(system_audio),
        )

        mic = self._normalize_audio(
            mic_audio[:length]
        )

        system = self._normalize_audio(
            system_audio[:length]
        )

        mic_gain = 0.50
        system_gain = 0.40

        mixed = (
            mic * mic_gain
            + system * system_gain
        )

        peak = np.max(
            np.abs(mixed)
        )

        if peak > 0:
            mixed = (
                mixed
                / peak
                * 0.90
            )

        return (
            mixed
            * 32767
        ).astype(np.int16)

    @staticmethod
    def _prepare_wav(
        audio: np.ndarray,
    ) -> np.ndarray:
        audio = audio.astype(
            np.float32
        )

        if len(audio) == 0:
            return np.array(
                [],
                dtype=np.int16,
            )

        peak = np.max(
            np.abs(audio)
        )

        if peak > 32767:
            audio = (
                audio
                / peak
                * 32767
            )

        audio = np.clip(
            audio,
            -32768,
            32767,
        )

        return audio.astype(
            np.int16
        )

    def _save_recordings(
        self,
        mic_audio: np.ndarray,
        system_audio: np.ndarray,
    ) -> None:
        mic_wav = self._prepare_wav(
            mic_audio
        )

        system_wav = self._prepare_wav(
            system_audio
        )

        mixed_wav = self._mix_audio(
            mic_audio,
            system_audio,
        )

        write(
            self.mic_file,
            TARGET_SAMPLE_RATE,
            mic_wav,
        )

        print(
            "Saved:",
            self.mic_file,
        )

        write(
            self.system_file,
            TARGET_SAMPLE_RATE,
            system_wav,
        )

        print(
            "Saved:",
            self.system_file,
        )

        write(
            self.mixed_file,
            TARGET_SAMPLE_RATE,
            mixed_wav,
        )

        print(
            "Saved:",
            self.mixed_file,
        )