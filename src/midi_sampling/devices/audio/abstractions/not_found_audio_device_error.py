class NotFoundAudioDeviceError(Exception):
    def __init__(self, device_name: str = None) -> None:
        self.device_name = device_name

    def __str__(self) -> str:
        if self.device_name:
            return f"Audio Device `{self.device_name}` is not found."
        else:
            return "Audio Device is not found."
