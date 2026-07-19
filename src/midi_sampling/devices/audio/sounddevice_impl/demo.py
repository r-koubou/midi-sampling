import typer

import sounddevice as sd

def main():
    devices = sorted(sd.query_devices(), key=lambda x: x["name"])
    for dev in devices:
        if dev["max_input_channels"] > 0:
            hostapi_info = sd.query_hostapis(dev["hostapi"])
            print(f"{dev['name']} ({hostapi_info['name']}) - Input Channels: {dev['max_input_channels']}")

if __name__ == "__main__":
    typer.run(main)
