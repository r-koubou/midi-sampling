import abc

from midi_sampling.devices.audio.abstractions.audio_device_information import AudioDeviceInformation


class AudioDeviceInformationLoader(metaclass=abc.ABCMeta):
    """
    Load AudioDeviceInformation from a file or other source.

    An abstract base class (not a Protocol) on purpose: implementing a
    loader must be visible as explicit inheritance, so that a class that
    merely happens to have a `load` method is never mistaken for one.
    """

    @abc.abstractmethod
    def load(self, file_path: str) -> AudioDeviceInformation:
        ...
