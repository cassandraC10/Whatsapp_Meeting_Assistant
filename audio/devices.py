import sounddevice as sd


def list_audio_devices():
    print("\n=== AVAILABLE AUDIO DEVICES ===\n")

    devices = sd.query_devices()

    for index, device in enumerate(devices):
        print(f"Device ID: {index}")
        print(f"Name: {device['name']}")
        print(f"Input channels: {device['max_input_channels']}")
        print(f"Output channels: {device['max_output_channels']}")
        print(f"Default sample rate: {device['default_samplerate']}")
        print("-" * 50)


if __name__ == "__main__":
    list_audio_devices()
