class NotFoundMidiDeviceError(Exception):
    def __init__(self, device_name: str = None):
        self.device_name = device_name

    def __str__(self):
        if self.device_name:
            return f"MIDI Device `{self.device_name}` is not found."
        else:
            return "MIDI Device is not found."
