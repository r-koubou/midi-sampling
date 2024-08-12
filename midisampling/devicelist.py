import sounddevice as sd
import rtmidi

midiout = rtmidi.MidiOut()
available_midi_ports = midiout.get_ports()

DIVIDER = "-" * 80

try:
    audio_devices = sd.query_devices()
    print(DIVIDER)
    print("Audio devices:")
    print(audio_devices)
    print(DIVIDER)
    for i, x in enumerate(audio_devices):
        print(i, x)

    print(DIVIDER)
    print("Audio Hosts(ASIO)")
    for x in sd.query_hostapis():
        if x['name'] == 'ASIO':
            print(x)

    if available_midi_ports:
        print(DIVIDER)
        print("MIDI devices:")
        for i in available_midi_ports:
            print(i)
    else:
        print("No MIDI devices found")
finally:
    del midiout