from pydantic import BaseModel
import yaml

from midi_sampling.devices.midi.abstractions.midi_device_information import (
    MidiDeviceInformationLoader,
    MidiDeviceInformation,
)


class _MidiDeviceInformationModel(BaseModel):
    device_name: str


class MidoMidiDeviceInformationLoader(MidiDeviceInformationLoader):
    """
    Load MidiDeviceInformation from a yaml file
    """

    def load(self, file_path: str) -> MidiDeviceInformation:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        model = _MidiDeviceInformationModel(**data)

        return MidiDeviceInformation(
            name=model.device_name,
        )
