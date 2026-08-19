import sounddevice as sd

print("\n=== HOST APIS ===")
for i, hostapi in enumerate(sd.query_hostapis()):
    print(f"\nHost API {i}:")
    print(hostapi)

print("\n=== DEVICES ===")
for i, device in enumerate(sd.query_devices()):
    print(
        f"{i}: {device['name']} | "
        f"inputs={device['max_input_channels']} | "
        f"outputs={device['max_output_channels']}"
    )