import threading
import time
from math import gcd
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
import sounddevice as sd
from scipy.io.wavfile import write
from scipy.signal import resample_poly

MIC_DEVICE_ID = 1

TARGET_SAMPLE_RATE = 44100
MIC_CHANNELS = 1
BLOCK_SIZE = 1024

NORMAL_STOP_TIMEOUT = 3
FORCED_STOP_TIMEOUT = 3


class MeetingRecorder:
    """
    Records local microphone audio and Windows system audio.

    The recorder keeps captured chunks in memory continuously so a
    stubborn audio thread cannot destroy an otherwise completed call.
    """

    def __init__(self, output_directory=None):
        self.output_directory = Path(
            output_directory or Path.cwd()
        )

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
        self.buffer_lock = threading.Lock()

        self.mic_thread = None
        self.system_thread = None

        self.mic_stream = None
        self.system_stream = None
        self.system_pyaudio = None

        self.mic_frames = []
        self.system_frames = []

        self.mic_error = None
        self.system_error = None

        self.system_sample_rate = None
        self.system_channels = None

        self.is_recording = False
        self.started_at = None

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def start(self):
        if self.is_recording:
            raise RuntimeError(
                "Recording is already running."
            )

        self._reset_state()

        self.is_recording = True
        self.started_at = time.time()

        self.mic_thread = threading.Thread(
            target=self._record_microphone,
            daemon=True,
            name="MicrophoneRecorder",
        )

        self.system_thread = threading.Thread(
            target=self._record_system_audio,
            daemon=True,
            name="SystemAudioRecorder",
        )

        print("Meeting recording started.")

        self.mic_thread.start()
        self.system_thread.start()

    def stop(self):
        """
        Stop recording and save everything captured so far.

        A slow/stuck audio shutdown is treated as recoverable.
        Captured audio is salvaged before any fatal error is raised.
        """

        if not self.is_recording:
            raise RuntimeError(
                "No meeting is currently recording."
            )

        print("Stopping meeting recording...")

        self.stop_event.set()

        mic_clean = self._stop_microphone_thread()
        system_clean = self._stop_system_thread()

        self.is_recording = False

        if not mic_clean:
            print(
                "Warning: microphone thread required "
                "forced shutdown."
            )

        if not system_clean:
            print(
                "Warning: system audio thread did not "
                "stop normally. Salvaging captured audio."
            )

        print("Recovering captured audio...")

        mic_audio = self._build_microphone_audio()
        system_audio = self._build_system_audio()

        # Save whatever is recoverable before failing.
        if mic_audio is None and system_audio is None:
            raise RuntimeError(
                "No usable audio was captured."
            )

        if mic_audio is None:
            raise RuntimeError(
                "Microphone audio could not be recovered."
            )

        if system_audio is None:
            # Preserve the microphone recording even if
            # the remote track failed completely.
            self._save_mic_only(
                mic_audio
            )

            raise RuntimeError(
                "Your microphone recording was saved, "
                "but no usable system audio was captured."
            )

        system_audio = self._resample_audio(
            system_audio,
            self.system_sample_rate,
            TARGET_SAMPLE_RATE,
        )

        mic_audio = mic_audio.astype(
            np.float32
        )

        minimum_length = min(
            len(mic_audio),
            len(system_audio),
        )

        if minimum_length <= 0:
            raise RuntimeError(
                "Captured audio contains no usable samples."
            )

        mic_audio = mic_audio[
            :minimum_length
        ]

        system_audio = system_audio[
            :minimum_length
        ]

        print("Saving recovered audio...")

        self._save_recordings(
            mic_audio,
            system_audio,
        )

        duration = (
            minimum_length
            / TARGET_SAMPLE_RATE
        )

        print(
            f"Recording saved successfully. "
            f"Duration: {duration:.1f} seconds."
        )

        if self.mic_error:
            print(
                "Microphone warning:",
                self.mic_error,
            )

        if self.system_error:
            print(
                "System audio warning:",
                self.system_error,
            )

        return {
            "mic": self.mic_file,
            "system": self.system_file,
            "mixed": self.mixed_file,
            "duration": duration,
            "mic_shutdown_clean": mic_clean,
            "system_shutdown_clean": system_clean,
        }

    def elapsed_seconds(self):
        if (
            not self.is_recording
            or self.started_at is None
        ):
            return 0

        return int(
            time.time() - self.started_at
        )

    # ---------------------------------------------------------
    # Reset
    # ---------------------------------------------------------

    def _reset_state(self):
        self.stop_event.clear()

        with self.buffer_lock:
            self.mic_frames = []
            self.system_frames = []

        self.mic_error = None
        self.system_error = None

        self.system_sample_rate = None
        self.system_channels = None

        self.mic_stream = None
        self.system_stream = None
        self.system_pyaudio = None

    # ---------------------------------------------------------
    # Microphone
    # ---------------------------------------------------------

    def _record_microphone(self):
        try:
            print(
                "Microphone recording thread started."
            )

            with sd.InputStream(
                samplerate=TARGET_SAMPLE_RATE,
                channels=MIC_CHANNELS,
                dtype="int16",
                device=MIC_DEVICE_ID,
                blocksize=BLOCK_SIZE,
            ) as stream:

                self.mic_stream = stream

                while not self.stop_event.is_set():
                    data, overflowed = stream.read(
                        BLOCK_SIZE
                    )

                    if overflowed:
                        print(
                            "Warning: microphone "
                            "buffer overflow."
                        )

                    with self.buffer_lock:
                        self.mic_frames.append(
                            data.copy()
                        )

            print(
                "Microphone recording thread stopped."
            )

        except Exception as error:
            # Forced shutdown can cause read/stream errors.
            # That is not fatal if stop was already requested.
            if self.stop_event.is_set():
                print(
                    "Microphone stream closed during stop."
                )
            else:
                self.mic_error = error

                print(
                    "Microphone recording error:",
                    error,
                )

        finally:
            self.mic_stream = None

    # ---------------------------------------------------------
    # System / WASAPI
    # ---------------------------------------------------------

    def _find_loopback_device(self, audio):
        wasapi = (
            audio.get_host_api_info_by_type(
                pyaudio.paWASAPI
            )
        )

        output_index = wasapi[
            "defaultOutputDevice"
        ]

        output_device = (
            audio.get_device_info_by_index(
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

        for loopback in (
            audio
            .get_loopback_device_info_generator()
        ):
            if (
                output_device["name"]
                in loopback["name"]
            ):
                print(
                    "Using WASAPI loopback:",
                    loopback["name"],
                )

                return loopback

        raise RuntimeError(
            "Could not find a WASAPI loopback "
            "device for the current output."
        )

    def _record_system_audio(self):
        audio = pyaudio.PyAudio()

        self.system_pyaudio = audio

        try:
            print(
                "System audio recording thread started."
            )

            device = self._find_loopback_device(
                audio
            )

            self.system_sample_rate = int(
                device["defaultSampleRate"]
            )

            self.system_channels = int(
                device["maxInputChannels"]
            )

            print(
                "System sample rate:",
                self.system_sample_rate,
            )

            print(
                "System channels:",
                self.system_channels,
            )

            stream = audio.open(
                format=pyaudio.paInt16,
                channels=self.system_channels,
                rate=self.system_sample_rate,
                input=True,
                input_device_index=device[
                    "index"
                ],
                frames_per_buffer=BLOCK_SIZE,
            )

            self.system_stream = stream

            while not self.stop_event.is_set():
                data = stream.read(
                    BLOCK_SIZE,
                    exception_on_overflow=False,
                )

                # Store immediately.
                # We no longer wait until the thread exits.
                with self.buffer_lock:
                    self.system_frames.append(
                        bytes(data)
                    )

            print(
                "System audio recording thread stopped."
            )

        except Exception as error:
            # A forced close often makes stream.read()
            # raise. If we're already stopping, that is
            # expected and captured frames remain usable.
            if self.stop_event.is_set():
                print(
                    "System audio stream closed "
                    "during shutdown."
                )
            else:
                self.system_error = error

                print(
                    "System recording error:",
                    error,
                )

        finally:
            self._close_system_stream()

            try:
                audio.terminate()
            except Exception:
                pass

            self.system_pyaudio = None

    # ---------------------------------------------------------
    # Thread shutdown
    # ---------------------------------------------------------

    def _stop_microphone_thread(self):
        if self.mic_thread is None:
            return True

        print(
            "Waiting for microphone thread..."
        )

        self.mic_thread.join(
            timeout=NORMAL_STOP_TIMEOUT
        )

        if not self.mic_thread.is_alive():
            print(
                "Microphone alive after stop: False"
            )
            return True

        print(
            "Microphone still active. "
            "Forcing stream shutdown..."
        )

        try:
            if self.mic_stream is not None:
                self.mic_stream.abort()
        except Exception as error:
            print(
                "Microphone force-stop warning:",
                error,
            )

        self.mic_thread.join(
            timeout=FORCED_STOP_TIMEOUT
        )

        alive = self.mic_thread.is_alive()

        print(
            "Microphone alive after forced stop:",
            alive,
        )

        # Do not throw here.
        # stop() will salvage the buffered frames.
        return not alive

    def _stop_system_thread(self):
        if self.system_thread is None:
            return True

        print(
            "Waiting for system audio thread..."
        )

        self.system_thread.join(
            timeout=NORMAL_STOP_TIMEOUT
        )

        if not self.system_thread.is_alive():
            print(
                "System audio alive after stop: False"
            )
            return True

        print(
            "System audio is still active. "
            "Forcing WASAPI stream shutdown..."
        )

        self._close_system_stream()

        self.system_thread.join(
            timeout=FORCED_STOP_TIMEOUT
        )

        alive = self.system_thread.is_alive()

        print(
            "System audio alive after forced stop:",
            alive,
        )

        # Critical change:
        # a stubborn thread is now a warning,
        # not an automatic loss of the meeting.
        return not alive

    def _close_system_stream(self):
        stream = self.system_stream

        if stream is None:
            return

        # Remove shared reference first so we don't
        # repeatedly try to close the same stream.
        self.system_stream = None

        try:
            if stream.is_active():
                stream.stop_stream()
        except Exception:
            pass

        try:
            stream.close()
        except Exception:
            pass

    # ---------------------------------------------------------
    # Recover buffered audio
    # ---------------------------------------------------------

    def _build_microphone_audio(self):
        with self.buffer_lock:
            frames = list(
                self.mic_frames
            )

        if not frames:
            return None

        try:
            audio = np.concatenate(
                frames,
                axis=0,
            )

            return audio.flatten()

        except Exception as error:
            self.mic_error = error
            return None

    def _build_system_audio(self):
        with self.buffer_lock:
            frames = list(
                self.system_frames
            )

        if (
            not frames
            or not self.system_sample_rate
            or not self.system_channels
        ):
            return None

        try:
            raw_audio = np.frombuffer(
                b"".join(frames),
                dtype=np.int16,
            )

            channels = self.system_channels

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

            return raw_audio

        except Exception as error:
            self.system_error = error
            return None

    # ---------------------------------------------------------
    # Audio processing
    # ---------------------------------------------------------

    def _resample_audio(
        self,
        audio,
        original_rate,
        target_rate,
    ):
        original_rate = int(
            original_rate
        )

        target_rate = int(
            target_rate
        )

        if original_rate == target_rate:
            return audio.astype(
                np.float32
            )

        divisor = gcd(
            original_rate,
            target_rate,
        )

        up = (
            target_rate
            // divisor
        )

        down = (
            original_rate
            // divisor
        )

        return resample_poly(
            audio.astype(np.float32),
            up,
            down,
        ).astype(
            np.float32
        )

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

        mixed = (
            mic * 0.50
            +
            system * 0.40
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
        ).astype(
            np.int16
        )

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

        return np.clip(
            audio,
            -32768,
            32767,
        ).astype(
            np.int16
        )

    # ---------------------------------------------------------
    # Saving
    # ---------------------------------------------------------

    def _save_mic_only(
        self,
        mic_audio,
    ):
        mic_wav = self._prepare_wav(
            mic_audio
        )

        write(
            self.mic_file,
            TARGET_SAMPLE_RATE,
            mic_wav,
        )

        print(
            "Saved recoverable microphone audio:",
            self.mic_file.name,
        )

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

        print(
            "Saved:",
            self.mic_file.name,
        )

        print(
            "Saved:",
            self.system_file.name,
        )

        print(
            "Saved:",
            self.mixed_file.name,
        )