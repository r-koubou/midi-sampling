from device.RtmidiMidiDevice import RtmidiMidiDevice
from device.SdAudioDevice import SdAudioDevice

from prettytable import PrettyTable

audio_device = SdAudioDevice(None)
midi_device  = RtmidiMidiDevice(None)

table = PrettyTable()
table.align = "l"

try:
    table.title = "Audio Devices"
    table.field_names = ["Name", "Platform"]
    for x in audio_device.get_audio_devices():
        table.add_row([x.name, x.platform_name])
    print(table)

    table.clear()
    table.title = "MIDI Devices"
    table.field_names = ["Name"]
    for x in midi_device.get_midi_devices():
        table.add_row([x.name])
    print(table)

finally:
    audio_device.dispose()
    midi_device.dispose()
