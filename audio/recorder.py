import threading
import time
from math import gcd
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
import sounddevice as sd
from scipy.io.wavfile import write
from scipy.signal import resample_poly

# ============================================================
# CONFIG
# ============================================================

MIC_DEVICE_ID = 1

TARGET_SAMPLE_RATE = 44100
MIC_CHANNELS = 1
BLOCK_SIZE = 1024

# Maximum time we'll wait for each audio thread to close.
THREAD_STOP_TIMEOUT = 5


# ============================================================
# MEETING RECORDER
# ============================================================


class MeetingRecorder:
    """
    Reusable recorder for:

        local microphone
        +
        Windows/WASAPI system audio

    Public API:

        recorder = MeetingRecorder()

        recorder.start()

        ...

        result = recorder.stop()

    result contains:
        mic
        system
        mixed
        duration
    """

    def __init__(self, output_directory=None):

        if output_directory is None:
            output_directory = Path.cwd()

        self.output_directory = Path(output_directory)

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ----------------------------------------------------
        # OUTPUT FILES
        # ----------------------------------------------------

        self.mic_file = self.output_directory / "mic_raw.wav"

        self.system_file = self.output_directory / "system_raw.wav"

        self.mixed_file = self.output_directory / "meeting.wav"

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.stop_event = threading.Event()

        self.results = {}

        self.mic_thread = None
        self.system_thread = None

        self.is_recording = False

        self.started_at = None

    # ========================================================
    # PUBLIC: START
    # ========================================================

    def start(self):
        """
        Starts microphone and system recording.

        Returns immediately so a GUI can continue running.
        """

        if self.is_recording:

            raise RuntimeError("Recording is already running.")

        # Reset state from previous meeting.
        self.results = {}

        self.stop_event.clear()

        self.started_at = time.time()

        # ----------------------------------------------------
        # CREATE THREADS
        # ----------------------------------------------------

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

        # Set before starting so UI state is consistent.
        self.is_recording = True

        print("Meeting recording started.")

        self.mic_thread.start()
        self.system_thread.start()

    # ========================================================
    # PUBLIC: STOP
    # ========================================================

    def stop(self):
        """
        Stops both recording streams.

        Waits for the recording threads to close,
        but never waits forever.

        Then:
            - validates recordings
            - resamples system audio
            - saves mic_raw.wav
            - saves system_raw.wav
            - saves meeting.wav
        """

        if not self.is_recording:

            raise RuntimeError("No meeting is currently recording.")

        print("Stopping meeting recording...")

        # Tell both recording loops to exit.
        self.stop_event.set()

        # ----------------------------------------------------
        # WAIT FOR MICROPHONE
        # ----------------------------------------------------

        print("Waiting for microphone thread...")

        self.mic_thread.join(timeout=THREAD_STOP_TIMEOUT)

        mic_alive = self.mic_thread.is_alive()

        print(
            "Microphone alive after stop:",
            mic_alive,
        )

        # ----------------------------------------------------
        # WAIT FOR SYSTEM AUDIO
        # ----------------------------------------------------

        print("Waiting for system audio thread...")

        self.system_thread.join(timeout=THREAD_STOP_TIMEOUT)

        system_alive = self.system_thread.is_alive()

        print(
            "System audio alive after stop:",
            system_alive,
        )

        # We are no longer accepting this recorder
        # as an active recording session.
        self.is_recording = False

        # ----------------------------------------------------
        # THREAD FAILURE CHECK
        # ----------------------------------------------------

        if mic_alive:

            raise RuntimeError("Microphone recording thread " "did not stop cleanly.")

        if system_alive:

            raise RuntimeError("System audio recording thread " "did not stop cleanly.")

        # ----------------------------------------------------
        # RECORDING ERROR CHECK
        # ----------------------------------------------------

        self._check_errors()

        # ----------------------------------------------------
        # GET CAPTURED AUDIO
        # ----------------------------------------------------

        mic_audio = self.results["mic"]

        system_audio = self.results["system"]

        system_rate = self.results["system_sample_rate"]

        print("Preparing audio...")

        # ----------------------------------------------------
        # RESAMPLE SYSTEM AUDIO
        # ----------------------------------------------------

        system_audio = self._resample_audio(
            system_audio,
            system_rate,
            TARGET_SAMPLE_RATE,
        )

        mic_audio = mic_audio.astype(np.float32)

        # ----------------------------------------------------
        # ALIGN LENGTHS
        # ----------------------------------------------------

        minimum_length = min(
            len(mic_audio),
            len(system_audio),
        )

        if minimum_length <= 0:

            raise RuntimeError("Recording contains no usable audio.")

        mic_audio = mic_audio[:minimum_length]

        system_audio = system_audio[:minimum_length]

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        print("Saving audio files...")

        self._save_recordings(
            mic_audio,
            system_audio,
        )

        duration = minimum_length / TARGET_SAMPLE_RATE

        print(f"Recording saved. " f"Duration: {duration:.1f} seconds.")

        return {
            "mic": self.mic_file,
            "system": self.system_file,
            "mixed": self.mixed_file,
            "duration": duration,
        }

    # ========================================================
    # PUBLIC: ELAPSED TIME
    # ========================================================

    def elapsed_seconds(self):

        if not self.is_recording or self.started_at is None:

            return 0

        return int(time.time() - self.started_at)

    # ========================================================
    # MICROPHONE RECORDING
    # ========================================================

    def _record_microphone(self):

        frames = []

        try:

            print("Microphone recording thread started.")

            with sd.InputStream(
                samplerate=TARGET_SAMPLE_RATE,
                channels=MIC_CHANNELS,
                dtype="int16",
                device=MIC_DEVICE_ID,
                blocksize=BLOCK_SIZE,
            ) as stream:

                while not self.stop_event.is_set():

                    data, overflowed = stream.read(BLOCK_SIZE)

                    if overflowed:

                        print("Warning: microphone " "buffer overflow.")

                    frames.append(data.copy())

            if not frames:

                raise RuntimeError("No microphone audio captured.")

            audio = np.concatenate(
                frames,
                axis=0,
            )

            self.results["mic"] = audio.flatten()

            self.results["mic_sample_rate"] = TARGET_SAMPLE_RATE

            print("Microphone recording thread stopped.")

        except Exception as error:

            self.results["mic_error"] = error

            print(
                "Microphone recording error:",
                error,
            )

    # ========================================================
    # FIND WASAPI LOOPBACK DEVICE
    # ========================================================

    def _find_loopback_device(
        self,
        p,
    ):

        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)

        output_index = wasapi_info["defaultOutputDevice"]

        output_device = p.get_device_info_by_index(output_index)

        print(
            "Default Windows output:",
            output_device["name"],
        )

        # It may already be a loopback endpoint.
        if output_device.get(
            "isLoopbackDevice",
            False,
        ):

            return output_device

        # Otherwise locate corresponding loopback device.
        for loopback in p.get_loopback_device_info_generator():

            if output_device["name"] in loopback["name"]:

                print(
                    "Using WASAPI loopback:",
                    loopback["name"],
                )

                return loopback

        raise RuntimeError(
            "Could not find a WASAPI loopback " "device for the default output."
        )

    # ========================================================
    # SYSTEM AUDIO RECORDING
    # ========================================================

    def _record_system_audio(self):

        p = pyaudio.PyAudio()

        stream = None

        frames = []

        try:

            print("System audio recording " "thread started.")

            device = self._find_loopback_device(p)

            sample_rate = int(device["defaultSampleRate"])

            channels = int(device["maxInputChannels"])

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
                input_device_index=(device["index"]),
                frames_per_buffer=(BLOCK_SIZE),
            )

            while not self.stop_event.is_set():

                data = stream.read(
                    BLOCK_SIZE,
                    exception_on_overflow=False,
                )

                frames.append(data)

            if not frames:

                raise RuntimeError("No system audio captured.")

            raw_audio = np.frombuffer(
                b"".join(frames),
                dtype=np.int16,
            )

            # -----------------------------------------------
            # MULTICHANNEL -> MONO
            # -----------------------------------------------

            if channels > 1:

                usable_length = len(raw_audio) // channels * channels

                raw_audio = raw_audio[:usable_length]

                raw_audio = raw_audio.reshape(
                    -1,
                    channels,
                )

                raw_audio = raw_audio.mean(axis=1).astype(np.int16)

            self.results["system"] = raw_audio

            self.results["system_sample_rate"] = sample_rate

            print("System audio recording " "thread stopped.")

        except Exception as error:

            self.results["system_error"] = error

            print(
                "System recording error:",
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

    # ========================================================
    # ERROR CHECK
    # ========================================================

    def _check_errors(self):

        if "mic_error" in self.results:

            raise RuntimeError(
                "Microphone recording failed: " f"{self.results['mic_error']}"
            )

        if "system_error" in self.results:

            raise RuntimeError(
                "System recording failed: " f"{self.results['system_error']}"
            )

        if "mic" not in self.results:

            raise RuntimeError("Microphone produced no audio.")

        if "system" not in self.results:

            raise RuntimeError("System audio produced no audio.")

    # ========================================================
    # RESAMPLE
    # ========================================================

    def _resample_audio(
        self,
        audio,
        original_rate,
        target_rate,
    ):

        original_rate = int(original_rate)

        target_rate = int(target_rate)

        if original_rate == target_rate:

            return audio.astype(np.float32)

        common_divisor = gcd(
            original_rate,
            target_rate,
        )

        up = target_rate // common_divisor

        down = original_rate // common_divisor

        resampled = resample_poly(
            audio.astype(np.float32),
            up,
            down,
        )

        return resampled.astype(np.float32)

    # ========================================================
    # NORMALIZE
    # ========================================================

    def _normalize_audio(
        self,
        audio,
    ):

        audio = audio.astype(np.float32)

        if len(audio) == 0:

            return audio

        peak = np.max(np.abs(audio))

        if peak == 0:

            return audio

        return audio / peak

    # ========================================================
    # MIX
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

        mic = self._normalize_audio(mic_audio[:length])

        system = self._normalize_audio(system_audio[:length])

        # Adjust later if desired.
        mic_gain = 0.50
        system_gain = 0.40

        mixed = mic * mic_gain + system * system_gain

        peak = np.max(np.abs(mixed))

        if peak > 0:

            mixed = mixed / peak * 0.90

        mixed = mixed * 32767

        return mixed.astype(np.int16)

    # ========================================================
    # PREPARE WAV
    # ========================================================

    def _prepare_wav(
        self,
        audio,
    ):

        audio = audio.astype(np.float32)

        if len(audio) == 0:

            return np.array(
                [],
                dtype=np.int16,
            )

        peak = np.max(np.abs(audio))

        if peak > 32767:

            audio = audio / peak * 32767

        audio = np.clip(
            audio,
            -32768,
            32767,
        )

        return audio.astype(np.int16)

    # ========================================================
    # SAVE FILES
    # ========================================================

    def _save_recordings(
        self,
        mic_audio,
        system_audio,
    ):

        mic_wav = self._prepare_wav(mic_audio)

        system_wav = self._prepare_wav(system_audio)

        mixed_wav = self._mix_audio(
            mic_audio,
            system_audio,
        )

        # -----------------------------------------------
        # LOCAL / ME
        # -----------------------------------------------

        write(
            self.mic_file,
            TARGET_SAMPLE_RATE,
            mic_wav,
        )

        print(
            "Saved:",
            self.mic_file.name,
        )

        # -----------------------------------------------
        # REMOTE / CLIENT
        # -----------------------------------------------

        write(
            self.system_file,
            TARGET_SAMPLE_RATE,
            system_wav,
        )

        print(
            "Saved:",
            self.system_file.name,
        )

        # -----------------------------------------------
        # MIXED FALLBACK
        # -----------------------------------------------

        write(
            self.mixed_file,
            TARGET_SAMPLE_RATE,
            mixed_wav,
        )

        print(
            "Saved:",
            self.mixed_file.name,
        )
