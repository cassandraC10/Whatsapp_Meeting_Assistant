import threading
import time
from math import gcd
from pathlib import Path

import numpy as np
import sounddevice as sd
import pyaudiowpatch as pyaudio

from scipy.io.wavfile import write
from scipy.signal import resample_poly


# ============================================================
# CONFIG
# ============================================================

MIC_DEVICE_ID = 1

TARGET_SAMPLE_RATE = 44100
MIC_CHANNELS = 1
BLOCK_SIZE = 1024


# ============================================================
# MEETING RECORDER
# ============================================================

class MeetingRecorder:
    """
    Reusable meeting recorder.

    Usage:

        recorder = MeetingRecorder()
        recorder.start()

        ...

        recorder.stop()

    Produces:
        mic_raw.wav
        system_raw.wav
        meeting.wav
    """

    def __init__(self, output_directory=None):

        if output_directory is None:
            output_directory = Path.cwd()

        self.output_directory = Path(output_directory)

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

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

        self.results = {}

        self.mic_thread = None
        self.system_thread = None

        self.is_recording = False

        self.started_at = None


    # ========================================================
    # PUBLIC API
    # ========================================================

    def start(self):
        """
        Starts microphone + system recording.

        Returns immediately.
        """

        if self.is_recording:
            raise RuntimeError(
                "Recording is already running."
            )

        self.results = {}

        self.stop_event.clear()

        self.started_at = time.time()

        self.mic_thread = threading.Thread(
            target=self._record_microphone,
            daemon=True,
        )

        self.system_thread = threading.Thread(
            target=self._record_system_audio,
            daemon=True,
        )

        self.mic_thread.start()
        self.system_thread.start()

        self.is_recording = True

        print("Meeting recording started.")


    def stop(self):
        """
        Stops recording, processes audio,
        saves all WAV files, and returns
        their paths.
        """

        if not self.is_recording:
            raise RuntimeError(
                "No meeting is currently recording."
            )

        print("Stopping meeting recording...")

        self.stop_event.set()

        self.mic_thread.join()
        self.system_thread.join()

        self.is_recording = False

        self._check_errors()

        mic_audio = self.results["mic"]

        system_audio = self.results["system"]

        system_rate = self.results[
            "system_sample_rate"
        ]

        system_audio = self._resample_audio(
            system_audio,
            system_rate,
            TARGET_SAMPLE_RATE,
        )

        mic_audio = mic_audio.astype(
            np.float32
        )

        # Align track lengths
        minimum_length = min(
            len(mic_audio),
            len(system_audio),
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
            f"Duration: {duration:.1f} seconds."
        )

        return {
            "mic": self.mic_file,
            "system": self.system_file,
            "mixed": self.mixed_file,
            "duration": duration,
        }


    def elapsed_seconds(self):
        """
        Returns current recording duration.
        """

        if not self.is_recording:
            return 0

        return int(
            time.time() - self.started_at
        )


    # ========================================================
    # MICROPHONE
    # ========================================================

    def _record_microphone(self):

        frames = []

        try:

            with sd.InputStream(
                samplerate=TARGET_SAMPLE_RATE,
                channels=MIC_CHANNELS,
                dtype="int16",
                device=MIC_DEVICE_ID,
                blocksize=BLOCK_SIZE,
            ) as stream:

                while not self.stop_event.is_set():

                    data, overflowed = stream.read(
                        BLOCK_SIZE
                    )

                    if overflowed:
                        print(
                            "Microphone buffer overflow."
                        )

                    frames.append(
                        data.copy()
                    )

            if not frames:
                raise RuntimeError(
                    "No microphone audio captured."
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

        except Exception as error:

            self.results[
                "mic_error"
            ] = error


    # ========================================================
    # SYSTEM / WHATSAPP AUDIO
    # ========================================================

    def _find_loopback_device(self, p):

        wasapi_info = (
            p.get_host_api_info_by_type(
                pyaudio.paWASAPI
            )
        )

        output_index = (
            wasapi_info[
                "defaultOutputDevice"
            ]
        )

        output_device = (
            p.get_device_info_by_index(
                output_index
            )
        )

        if output_device.get(
            "isLoopbackDevice",
            False,
        ):
            return output_device

        for loopback in (
            p.get_loopback_device_info_generator()
        ):

            if (
                output_device["name"]
                in loopback["name"]
            ):
                return loopback

        raise RuntimeError(
            "Could not find WASAPI "
            "loopback device."
        )


    def _record_system_audio(self):

        p = pyaudio.PyAudio()

        stream = None

        try:

            device = (
                self._find_loopback_device(p)
            )

            sample_rate = int(
                device["defaultSampleRate"]
            )

            channels = int(
                device["maxInputChannels"]
            )

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=BLOCK_SIZE,
            )

            frames = []

            while not self.stop_event.is_set():

                data = stream.read(
                    BLOCK_SIZE,
                    exception_on_overflow=False,
                )

                frames.append(data)

            if not frames:
                raise RuntimeError(
                    "No system audio captured."
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

        except Exception as error:

            self.results[
                "system_error"
            ] = error

        finally:

            if stream is not None:

                stream.stop_stream()
                stream.close()

            p.terminate()


    # ========================================================
    # ERROR CHECK
    # ========================================================

    def _check_errors(self):

        if "mic_error" in self.results:

            raise RuntimeError(
                "Microphone recording failed: "
                f"{self.results['mic_error']}"
            )

        if "system_error" in self.results:

            raise RuntimeError(
                "System recording failed: "
                f"{self.results['system_error']}"
            )

        if "mic" not in self.results:

            raise RuntimeError(
                "Microphone produced no audio."
            )

        if "system" not in self.results:

            raise RuntimeError(
                "System produced no audio."
            )


    # ========================================================
    # RESAMPLING
    # ========================================================

    def _resample_audio(
        self,
        audio,
        original_rate,
        target_rate,
    ):

        if original_rate == target_rate:

            return audio.astype(
                np.float32
            )

        divisor = gcd(
            int(original_rate),
            int(target_rate),
        )

        up = (
            int(target_rate)
            // divisor
        )

        down = (
            int(original_rate)
            // divisor
        )

        return resample_poly(
            audio.astype(np.float32),
            up,
            down,
        )


    # ========================================================
    # NORMALIZATION
    # ========================================================

    def _normalize_audio(
        self,
        audio,
    ):

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


    # ========================================================
    # MIXING
    # ========================================================

    def _mix_audio(
        self,
        mic_audio,
        system_audio,
    ):

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
            +
            system * system_gain
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

        mixed = mixed * 32767

        return mixed.astype(
            np.int16
        )


    # ========================================================
    # WAV PREPARATION
    # ========================================================

    def _prepare_wav(
        self,
        audio,
    ):

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


    # ========================================================
    # SAVE
    # ========================================================

    def _save_recordings(
        self,
        mic_audio,
        system_audio,
    ):

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

        write(
            self.system_file,
            TARGET_SAMPLE_RATE,
            system_wav,
        )

        write(
            self.mixed_file,
            TARGET_SAMPLE_RATE,
            mixed_wav,
        )