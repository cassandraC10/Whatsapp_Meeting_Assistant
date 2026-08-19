import threading
import time
from math import gcd

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

MIC_RAW_FILE = "mic_raw.wav"
SYSTEM_RAW_FILE = "system_raw.wav"
MIXED_FILE = "meeting.wav"

BLOCK_SIZE = 1024


# ============================================================
# MICROPHONE RECORDING
# ============================================================

def record_microphone(results, stop_event):
    """
    Records the local microphone continuously
    until stop_event is triggered.
    """

    print("Microphone recording started...")

    frames = []

    try:
        with sd.InputStream(
            samplerate=TARGET_SAMPLE_RATE,
            channels=MIC_CHANNELS,
            dtype="int16",
            device=MIC_DEVICE_ID,
            blocksize=BLOCK_SIZE,
        ) as stream:

            while not stop_event.is_set():

                data, overflowed = stream.read(
                    BLOCK_SIZE
                )

                if overflowed:
                    print(
                        "Warning: microphone buffer overflow."
                    )

                frames.append(
                    data.copy()
                )

    except Exception as error:
        results["mic_error"] = error
        print(
            f"Microphone recording error: {error}"
        )
        return

    if not frames:
        results["mic_error"] = RuntimeError(
            "No microphone audio was captured."
        )
        return

    audio = np.concatenate(
        frames,
        axis=0
    )

    audio = audio.flatten()

    results["mic"] = audio
    results["mic_sample_rate"] = TARGET_SAMPLE_RATE

    print("Microphone recording finished.")


# ============================================================
# WASAPI LOOPBACK DEVICE
# ============================================================

def find_default_loopback_device(p):
    """
    Finds the loopback equivalent of the
    current default Windows WASAPI output.
    """

    wasapi_info = p.get_host_api_info_by_type(
        pyaudio.paWASAPI
    )

    default_output_index = wasapi_info[
        "defaultOutputDevice"
    ]

    default_output = p.get_device_info_by_index(
        default_output_index
    )

    print(
        f"Windows default output: "
        f"{default_output['name']}"
    )

    if default_output.get(
        "isLoopbackDevice",
        False
    ):
        return default_output

    for loopback in (
        p.get_loopback_device_info_generator()
    ):

        if (
            default_output["name"]
            in loopback["name"]
        ):
            return loopback

    raise RuntimeError(
        "Could not find WASAPI loopback device "
        "for the current Windows output."
    )


# ============================================================
# SYSTEM / WHATSAPP AUDIO RECORDING
# ============================================================

def record_system_audio(results, stop_event):
    """
    Records Windows/WhatsApp audio continuously
    using WASAPI loopback.
    """

    print("System audio recording started...")

    p = pyaudio.PyAudio()

    stream = None

    try:
        loopback_device = (
            find_default_loopback_device(p)
        )

        device_index = loopback_device["index"]

        sample_rate = int(
            loopback_device[
                "defaultSampleRate"
            ]
        )

        channels = int(
            loopback_device[
                "maxInputChannels"
            ]
        )

        print(
            f"Using loopback device: "
            f"{loopback_device['name']}"
        )

        print(
            f"System sample rate: "
            f"{sample_rate}"
        )

        print(
            f"System channels: "
            f"{channels}"
        )

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=BLOCK_SIZE,
        )

        frames = []

        while not stop_event.is_set():

            data = stream.read(
                BLOCK_SIZE,
                exception_on_overflow=False,
            )

            frames.append(data)

        if not frames:
            results["system_error"] = RuntimeError(
                "No system audio was captured."
            )
            return

        raw_bytes = b"".join(frames)

        system_audio = np.frombuffer(
            raw_bytes,
            dtype=np.int16,
        )

        # Convert stereo/multichannel audio to mono.
        if channels > 1:

            usable_length = (
                len(system_audio)
                // channels
                * channels
            )

            system_audio = system_audio[
                :usable_length
            ]

            system_audio = (
                system_audio.reshape(
                    -1,
                    channels,
                )
            )

            system_audio = (
                system_audio.mean(
                    axis=1
                )
                .astype(np.int16)
            )

        results["system"] = system_audio

        results[
            "system_sample_rate"
        ] = sample_rate

        print(
            "System audio recording finished."
        )

    except Exception as error:

        results["system_error"] = error

        print(
            f"System audio recording error: "
            f"{error}"
        )

    finally:

        if stream is not None:

            stream.stop_stream()
            stream.close()

        p.terminate()


# ============================================================
# RESAMPLING
# ============================================================

def resample_audio(
    audio,
    original_rate,
    target_rate,
):
    """
    Resamples an audio track using polyphase
    filtering.
    """

    if original_rate == target_rate:
        return audio.astype(np.float32)

    common_divisor = gcd(
        int(original_rate),
        int(target_rate),
    )

    up = (
        int(target_rate)
        // common_divisor
    )

    down = (
        int(original_rate)
        // common_divisor
    )

    resampled = resample_poly(
        audio.astype(np.float32),
        up,
        down,
    )

    return resampled.astype(
        np.float32
    )


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_audio(audio):
    """
    Converts an audio track into approximately
    the -1.0 to +1.0 range.
    """

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


# ============================================================
# MIXING
# ============================================================

def mix_audio(
    mic_audio,
    system_audio,
):
    """
    Creates a convenient mixed meeting track.

    mic_raw.wav and system_raw.wav remain the
    authoritative separated tracks.
    """

    length = min(
        len(mic_audio),
        len(system_audio),
    )

    mic = mic_audio[:length]

    system = system_audio[:length]

    mic = normalize_audio(mic)
    system = normalize_audio(system)

    # Tuning values.
    # We can adjust these after testing with headphones.
    mic_gain = 0.50
    system_gain = 0.40

    mixed = (
        mic * mic_gain
        +
        system * system_gain
    )

    mixed_peak = np.max(
        np.abs(mixed)
    )

    if mixed_peak > 0:

        mixed = (
            mixed
            / mixed_peak
            * 0.90
        )

    mixed = mixed * 32767

    return mixed.astype(
        np.int16
    )


# ============================================================
# WAV PREPARATION
# ============================================================

def prepare_for_wav(audio):
    """
    Safely converts audio into signed 16-bit
    PCM for writing as WAV.
    """

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


# ============================================================
# SAVE RECORDINGS
# ============================================================

def save_recordings(
    mic_audio,
    system_audio,
):
    """
    Saves all three files:

    mic_raw.wav
        Local speaker / you.

    system_raw.wav
        Remote speaker / WhatsApp audio.

    meeting.wav
        Combined fallback recording.
    """

    mic_for_wav = prepare_for_wav(
        mic_audio
    )

    system_for_wav = prepare_for_wav(
        system_audio
    )

    mixed_audio = mix_audio(
        mic_audio,
        system_audio,
    )

    write(
        MIC_RAW_FILE,
        TARGET_SAMPLE_RATE,
        mic_for_wav,
    )

    print(
        f"Saved local microphone: "
        f"{MIC_RAW_FILE}"
    )

    write(
        SYSTEM_RAW_FILE,
        TARGET_SAMPLE_RATE,
        system_for_wav,
    )

    print(
        f"Saved remote/system audio: "
        f"{SYSTEM_RAW_FILE}"
    )

    write(
        MIXED_FILE,
        TARGET_SAMPLE_RATE,
        mixed_audio,
    )

    print(
        f"Saved combined meeting: "
        f"{MIXED_FILE}"
    )


# ============================================================
# MAIN RECORDER
# ============================================================

def record_meeting():

    print()
    print(
        "========================================"
    )
    print(
        "      WhatsApp Meeting Recorder"
    )
    print(
        "========================================"
    )
    print()

    print(
        "Recommended: use headphones during "
        "the WhatsApp call."
    )

    print()

    input(
        "Press ENTER when you are ready "
        "to START recording..."
    )

    stop_event = threading.Event()

    results = {}

    mic_thread = threading.Thread(
        target=record_microphone,
        args=(
            results,
            stop_event,
        ),
    )

    system_thread = threading.Thread(
        target=record_system_audio,
        args=(
            results,
            stop_event,
        ),
    )

    print()
    print(
        "========================================"
    )
    print(
        "              RECORDING"
    )
    print(
        "========================================"
    )

    print()

    print(
        "Microphone       -> ME"
    )

    print(
        "WhatsApp/System  -> REMOTE"
    )

    print()

    print(
        "Press ENTER when you want to STOP."
    )

    print()

    start_time = time.time()

    mic_thread.start()
    system_thread.start()

    # This blocks until the user presses Enter.
    input()

    print()
    print("Stopping recording...")

    stop_event.set()

    # Wait for both recording threads
    # to close cleanly.
    mic_thread.join()
    system_thread.join()

    elapsed = time.time() - start_time

    print(
        f"Recorded approximately "
        f"{elapsed:.1f} seconds."
    )

    # ========================================================
    # ERROR CHECKING
    # ========================================================

    if "mic_error" in results:

        raise RuntimeError(
            "Microphone recording failed: "
            f"{results['mic_error']}"
        )

    if "system_error" in results:

        raise RuntimeError(
            "System recording failed: "
            f"{results['system_error']}"
        )

    if "mic" not in results:

        raise RuntimeError(
            "Microphone recording produced "
            "no audio."
        )

    if "system" not in results:

        raise RuntimeError(
            "System recording produced "
            "no audio."
        )

    # ========================================================
    # GET AUDIO
    # ========================================================

    mic_audio = results["mic"]

    system_audio = results["system"]

    system_rate = results[
        "system_sample_rate"
    ]

    print()
    print("Preparing recording...")

    # ========================================================
    # RESAMPLE SYSTEM TRACK
    # ========================================================

    system_audio = resample_audio(
        system_audio,
        system_rate,
        TARGET_SAMPLE_RATE,
    )

    mic_audio = mic_audio.astype(
        np.float32
    )

    # ========================================================
    # ALIGN TRACK LENGTHS
    # ========================================================

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

    # ========================================================
    # SAVE
    # ========================================================

    print("Saving audio files...")

    save_recordings(
        mic_audio,
        system_audio,
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    final_duration = (
        minimum_length
        / TARGET_SAMPLE_RATE
    )

    print()
    print(
        "========================================"
    )
    print(
        "               SUCCESS"
    )
    print(
        "========================================"
    )

    print()

    print(
        f"Final audio duration: "
        f"{final_duration:.1f} seconds"
    )

    print()

    print(
        "ME:"
    )
    print(
        f"  {MIC_RAW_FILE}"
    )

    print()

    print(
        "REMOTE / CLIENT:"
    )
    print(
        f"  {SYSTEM_RAW_FILE}"
    )

    print()

    print(
        "COMBINED:"
    )
    print(
        f"  {MIXED_FILE}"
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    record_meeting()