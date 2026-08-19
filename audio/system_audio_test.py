import pyaudiowpatch as pyaudio
import wave

DURATION = 10
OUTPUT_FILE = "system_audio_test.wav"

p = pyaudio.PyAudio()

print("\n=== WASAPI LOOPBACK DEVICES ===\n")

loopback_devices = []

for device in p.get_loopback_device_info_generator():
    loopback_devices.append(device)

    print(f"Device index: {device['index']}")
    print(f"Name: {device['name']}")
    print(f"Channels: {device['maxInputChannels']}")
    print(f"Sample rate: {device['defaultSampleRate']}")
    print("-" * 50)

if not loopback_devices:
    print("No loopback devices found.")
    p.terminate()
    raise SystemExit

device = loopback_devices[0]

device_index = device["index"]
sample_rate = int(device["defaultSampleRate"])
channels = device["maxInputChannels"]

print(f"\nUsing loopback device: {device['name']}")
print("Play some audio from your computer now...")

stream = p.open(
    format=pyaudio.paInt16,
    channels=channels,
    rate=sample_rate,
    input=True,
    input_device_index=device_index,
    frames_per_buffer=1024,
)

frames = []

for _ in range(int(sample_rate / 1024 * DURATION)):
    data = stream.read(1024, exception_on_overflow=False)
    frames.append(data)

stream.stop_stream()
stream.close()

with wave.open(OUTPUT_FILE, "wb") as wf:
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(sample_rate)
    wf.writeframes(b"".join(frames))

p.terminate()

print(f"\nSaved: {OUTPUT_FILE}")