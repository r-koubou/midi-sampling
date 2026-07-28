import abc

from midi_sampling.devices.midi.abstractions.midi_device_information import MidiDeviceInformation


class MidiDeviceInformationLoader(metaclass=abc.ABCMeta):
    """
    Load MidiDeviceInformation from a file or other source.

    An abstract base class (not a Protocol) on purpose: implementing a
    loader must be visible as explicit inheritance, so that a class that
    merely happens to have a `load` method is never mistaken for one.
    """

    @abc.abstractmethod
    def load(self, file_path: str) -> MidiDeviceInformation:
        ...
