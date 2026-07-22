import abc

class AudioDevice(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def initialize(self) -> None:
        """
        Initialize the Audio device.
        """
        pass

    @abc.abstractmethod
    def dispose(self) -> None:
        """
        Release resources.
        (e.g. Audio device, native resources etc.)
        """
        pass

    @abc.abstractmethod
    def start_recording(self, duration: float) -> None:
        """
        Start recording audio for the given duration in seconds.
        This function should be non-blocking.
        """
        pass

    @abc.abstractmethod
    def stop_recording(self) -> None:
        """
        Stop recording audio.
        """
        pass

    @abc.abstractmethod
    def export_audio(self, file_path: str) -> None:
        """
        Export recorded audio to a file.
        """
        pass
