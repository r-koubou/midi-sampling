from typing import List, override
import abc
import math
import os
import time
from logging import getLogger

import midisampling.waveprocess.normalize as normalize
import midisampling.waveprocess.trim as trim

from midisampling.device.mididevice import IMidiDevice
from midisampling.device.MidoMidiDevice import MidoMidiDevice

from midisampling.device.audiodevice import IAudioDevice, AudioDeviceOption, AudioDataFormat
from midisampling.device.SdAudioDevice import SdAudioDevice


from midisampling.appconfig.sampling import SamplingConfig
from midisampling.appconfig.midi import MidiConfig, SampleZone, VelocityLayer, ProgramChange

import midisampling.dynamic_format as dynamic_format

from midisampling.exportpath import RecordedAudioPath
from midisampling.appconfig.audioprocess import AudioProcessConfig
from midisampling.waveprocess.processing import process as run_postprocess

import midisampling.notenumber as notenumber_util


THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = getLogger(__name__)


class SamplingArguments:
    """
    Composite of sampling, MIDI, and post process configurations.
    """
    def __init__(self, sampling_config_path: str, midi_config_path: str, postprocess_config_path:str = None, overwrite_recorded: bool = False):
        self.sampling_config_path = sampling_config_path
        self.midi_config_path = midi_config_path
        self.postprocess_config_path = postprocess_config_path
        self.overwrite_recorded = overwrite_recorded


class ISampling(abc.ABC):

    @abc.abstractmethod
    def initialize(self) -> None:
        """
        Initialize sampling
        """
        pass

    @abc.abstractmethod
    def dispose(self) -> None:
        """
        Dispose resources in sampling
        """
        pass

    @abc.abstractmethod
    def create_audio_device(self) -> IAudioDevice:
        """
        Create audio device

        Returns
        -------
            IAudioDevice: Audio device
        """
        pass

    @abc.abstractmethod
    def create_midi_device(self) -> IMidiDevice:
        """
        Create MIDI device

        Returns
        -------
            IMidiDevice: MIDI device
        """

    @abc.abstractmethod
    def execute(self) -> None:
        """
        The sampling entry point.

        In most cases, the following order of processing is assumed.
        However, this order may vary depending on the implementation.

        1. `self.pre_send_smf()`
        - Send MIDI from file to device before sampling
        2. `self.pre_sampling()`
        - Perform any necessary setup before the sampling process
        3. For each program change:
        - `self.send_progam_change()`
        - Send program change to the MIDI device
        4. For each sample zone:
        - For each velocity layer:
            - `self.sample()`
            - Perform the actual sampling for the current program, zone, and velocity
        5. `self.post_process()`
        - Perform post-processing on all recorded samples
        """
        pass

    @abc.abstractmethod
    def pre_sampling(self):
        """
        Do something before sampling process once.
        """
        pass

    @abc.abstractmethod
    def pre_send_smf(self):
        """
        Sending MIDI from file.
        Call before sampling process once.
        """
        pass

    @abc.abstractmethod
    def send_progam_change(self, channel: int, program: ProgramChange):
        """
        Send program change to device
        """
        pass

    @abc.abstractmethod
    def sample(self, program: ProgramChange, zone: SampleZone, velocity: VelocityLayer, recorded_path_list: List[RecordedAudioPath]) -> None:
        """
        Invidual sampling process. Play MIDI and record audio.

        Parameters
        ----------
        program : ProgramChange
            Program change information used for sampling
        zone : SampleZone
            Key zone to be sampled
        velocity : VelocityLayer
            Velocity layer to be sampled
        recorded_path_list : List[RecordedAudioPath]
            List of recorded audio paths
            Append recorded audio path to this list
        """
        pass

    def validate_recorded_file(self, this_time_recorded_path: RecordedAudioPath, recorded_path_list: List[RecordedAudioPath]):
        """
        Validate recorded file before export recorded file.
        In this class, the implementation checks if the file already exists & if output was done during this sampling process.

        Parameters
        ----------
        this_time_recorded_path : RecordedAudioPath
            Recorded audio path to be exported

        recorded_path_list : List[RecordedAudioPath]
            List of previous recorded audio paths
        """
        # Check duplicate sample zone or already recorded file
        # If overwrite_recorded is False, raise exception
        if not self.overwrite_recorded:
            if(this_time_recorded_path in recorded_path_list):
                raise ValueError(f"Duplecate sample zone(s) defined in midi-sampling-config file. {this_time_recorded_path.path()}")
            if(os.path.exists(this_time_recorded_path.path())):
                raise FileExistsError(f"Recorded file already exists. {this_time_recorded_path.path()}")
        else:
            if(this_time_recorded_path in recorded_path_list):
                logger.warning(f"Overwrite recorded file. {this_time_recorded_path.path()}")
            if(os.path.exists(this_time_recorded_path.path())):
                logger.warning(f"Overwrite recorded file. {this_time_recorded_path.path()}")

    @abc.abstractmethod
    def post_process(self, config: AudioProcessConfig, recorded_path_list: List[RecordedAudioPath], processed_output_dir: str):
        """
        Post process recorded audio data
        """
        pass

    @classmethod
    def expand_path_placeholder(self, format_string:str, pc_msb:int, pc_lsb:int, pc_value, key_root: int, key_low: int, key_high: int, min_velocity:int, max_velocity:int, velocity: int, use_scale_spn_format: bool):
        """
        Expand placeholders in format_string with given values

        Parameters
        ----------
            format_string (str): string.format compatible format string. available placeholders are
                {pc_msb}, {pc_lsb}, {pc},
                {key_root}, {key_low}, {key_high},
                {key_root_scale}, {key_low_scale}, {key_high_scale},
                {velocity}, {min_velocity}, {max_velocity}
                and Python format specifiers are also available.
            pc_msb (int): Program Change MSB
            pc_lsb (int): Program Change LSB
            pc_value: Program Change Value
            key_root (int): Zone: Root key (Send as MIDI note number to device)
            key_low (int): Zone: Low key
            key_high (int): Zone: High key
            min_velocity (int): Velocity Layer: Minimum definition
            max_velocity (int): Velocity Layer: Maximum definition
            velocity (int): Send as MIDI velocity to device
            use_scale_spn_format (bool): True: Scientific pitch notation format, False: Yamaha format

        Returns
        -------
            str: formatted string
        """

        format_value = {
            # MIDI Controll Change
            "pc_msb": pc_msb,
            "pc_lsb": pc_lsb,
            "pc": pc_value,
            # MIDI Note number
            "key_root": key_root,
            "key_low": key_low,
            "key_high": key_high,
            # Note name
            "key_root_scale": notenumber_util.as_scalename(key_root, spn_format=use_scale_spn_format),
            "key_low_scale": notenumber_util.as_scalename(key_low, spn_format=use_scale_spn_format),
            "key_high_scale": notenumber_util.as_scalename(key_high, spn_format=use_scale_spn_format),
            # MIDI Velocity
            "velocity": velocity,
            "min_velocity": min_velocity,
            "max_velocity": max_velocity,
        }

        return dynamic_format.format(format_string=format_string, data=format_value)

class SamplingBase(ISampling):
    """
    Common implementation for sampling
    """
    def __init__(self, sampling_config: SamplingConfig, midi_config: MidiConfig, postprocess_config: AudioProcessConfig, overwrite_recorded: bool = False):
        self.sampling_config = sampling_config
        self.midi_config = midi_config
        self.postprocess_config = postprocess_config
        self.overwrite_recorded = overwrite_recorded

        self.audio_device: IAudioDevice = None
        self.midi_device: IMidiDevice = None

    @override
    def initialize(self) -> None:
        #---------------------------------------------------------------------------
        # MIDI
        #---------------------------------------------------------------------------
        self.midi_device = self.create_midi_device()
        self.midi_device.initialize()

        #---------------------------------------------------------------------------
        # Audio
        #---------------------------------------------------------------------------
        self.audio_device = self.create_audio_device()
        self.audio_device.initialize()

    @override
    def dispose(self) -> None:
        try:
            if self.midi_device:
                self.midi_device.dispose()
        finally:
            pass

        try:
            if self.audio_device:
                self.audio_device.dispose()
        finally:
            pass

    @override
    def execute(self) -> None:
        """
        Execute sampling
        """

        program_change_list     = self.midi_config.program_change_list
        midi_channel            = self.midi_config.midi_channel
        sample_zone             = self.midi_config.sample_zone
        processed_output_dir    = self.midi_config.processed_output_dir

        # Calculate total sampling count
        total_sampling_count = len(program_change_list) * SampleZone.get_total_sample_count(sample_zone)

        if total_sampling_count == 0:
            logger.warning("No sampling target (Sample zone is empty)")
            return

        #---------------------------------------------------------------------------
        # Sampling
        #---------------------------------------------------------------------------

        # Send MIDI from file to device before sampling
        self.pre_send_smf()

        # Do something before sampling process once.
        self.pre_sampling()

        recorded_path_list: List[RecordedAudioPath] = []

        logger.info("Sampling...")

        process_count = 1

        for program in program_change_list:
            # Send program change
            logger.info(f"Program Change - MSB: {program.msb}, LSB: {program.lsb}, Program: {program.program}")
            self.send_progam_change(midi_channel, program)

            for zone in sample_zone:
                for velocity in zone.velocity_layers:
                    logger.info(f"[{process_count: 4d} / {total_sampling_count:4d}] Note on - Channel: {midi_channel:2d}, Note: {zone.key_root:3d}, Velocity: {velocity.send_velocity:3d} (Key Low:{zone.key_low:3d}, Key High:{zone.key_high:3d}, Min Velocity:{velocity.min_velocity:3d}, Max Velocity:{velocity.max_velocity:3d})")
                    self.sample(program, zone, velocity, recorded_path_list)

                    process_count += 1

        #---------------------------------------------------------------------------
        # Post Process
        #---------------------------------------------------------------------------
        logger.info("#" * 80)
        logger.info("Post process")
        logger.info("#" * 80)
        self.post_process(self.postprocess_config, recorded_path_list, processed_output_dir)


class DefaultSampling(SamplingBase):
    """
    Default implementation of the ISampling interface
    """
    def __init__(self, sampling_config: SamplingConfig, midi_config: MidiConfig, postprocess_config: AudioProcessConfig, overwrite_recorded: bool = False):
        super().__init__(sampling_config, midi_config, postprocess_config, overwrite_recorded)

    @override
    def create_midi_device(self) -> IMidiDevice:
        return MidoMidiDevice(self.sampling_config.midi_out_device)

    @override
    def create_audio_device(self) -> IAudioDevice:
        audio_data_format = AudioDataFormat.parse(
            f"{self.sampling_config.audio_sample_bits_format}{self.sampling_config.audio_sample_bits}"
        )

        audio_option: AudioDeviceOption = AudioDeviceOption(
            device_name=self.sampling_config.audio_in_device,
            device_platform=self.sampling_config.audio_in_device_platform,
            sample_rate=self.sampling_config.audio_sample_rate,
            channels=self.sampling_config.audio_channels,
            data_format=audio_data_format,
            input_ports=self.sampling_config.asio_audio_ins
        )
        return SdAudioDevice(audio_option)

    @override
    def pre_sampling(self):
        os.makedirs(self.midi_config.output_dir, exist_ok=True)

    @override
    def pre_send_smf(self):
        pre_send_smf_path_list = self.midi_config.pre_send_smf_path_list

        # Send MIDI from file to device before sampling
        if len(pre_send_smf_path_list) > 0:
            for file in pre_send_smf_path_list:
                logger.info(f"Send MIDI from file: {file}")
                self.midi_device.send_message_from_file(file)

    @override
    def send_progam_change(self, channel: int, program: ProgramChange):
        self.midi_device.send_progam_change(channel, program.msb, program.lsb, program.program)

    @override
    def sample(self, program: ProgramChange, zone: SampleZone, velocity: VelocityLayer, recorded_path_list: List[RecordedAudioPath]) -> None:
        midi_channel          = self.midi_config.midi_channel
        midi_note_duration    = self.midi_config.midi_note_duration
        midi_pre_duration     = self.midi_config.midi_pre_wait_duration
        midi_release_duration = self.midi_config.midi_release_duration
        scale_name_format     = self.midi_config.scale_name_format
        output_dir            = self.midi_config.output_dir

        # Record Audio
        record_duration = math.floor(midi_pre_duration + midi_note_duration + midi_release_duration)

        self.audio_device.start_recording(record_duration)
        time.sleep(midi_pre_duration)

        # Play MIDI
        self.midi_device.play_note(midi_channel, zone.key_root, velocity.send_velocity, midi_note_duration)

        time.sleep(midi_release_duration)

        self.audio_device.stop_recording()

        # Save Audio
        output_file_path = ISampling.expand_path_placeholder(
            format_string=self.midi_config.output_prefix_format,
            pc_msb=program.msb,
            pc_lsb=program.lsb,
            pc_value=program.program,
            key_root=zone.key_root,
            key_low=zone.key_low,
            key_high=zone.key_high,
            min_velocity=velocity.min_velocity,
            max_velocity=velocity.max_velocity,
            velocity=velocity.send_velocity,
            use_scale_spn_format=scale_name_format == "SPN"
        )

        export_path = RecordedAudioPath(base_dir=output_dir, file_path=output_file_path + ".wav")
        export_path.makedirs()

        logger.debug(f"  -> Export recorded data to: {export_path.path()}")

        self.validate_recorded_file(export_path, recorded_path_list)

        self.audio_device.export_audio(export_path.path())
        recorded_path_list.append(export_path)

    @override
    def post_process(self, config: AudioProcessConfig, recorded_path_list: List[RecordedAudioPath], processed_output_dir: str):
        run_postprocess(
            config=config,
            recorded_files=recorded_path_list,
            output_dir=processed_output_dir
        )

class DryRunSampling(SamplingBase):
    """
    Dry run implementation of the ISampling interface.
    This class does not perform actual sampling. But print out the sampling process.
    """
    def __init__(self, sampling_config: SamplingConfig, midi_config: MidiConfig, postprocess_config: AudioProcessConfig, overwrite_recorded: bool = False):
        super().__init__(sampling_config, midi_config, postprocess_config, overwrite_recorded)

    @override
    def initialize(self) -> None:
        pass

    @override
    def create_midi_device(self) -> IMidiDevice:
        return None

    @override
    def create_audio_device(self) -> IAudioDevice:
        return None

    @override
    def pre_sampling(self):
        pass

    @override
    def pre_send_smf(self):
        pass

    @override
    def send_progam_change(self, channel: int, program: ProgramChange):
        pass

    @override
    def sample(self, program: ProgramChange, zone: SampleZone, velocity: VelocityLayer, recorded_path_list: List[RecordedAudioPath]) -> None:
        scale_name_format = self.midi_config.scale_name_format
        output_dir        = self.midi_config.output_dir

        output_file_path = ISampling.expand_path_placeholder(
            format_string=self.midi_config.output_prefix_format,
            pc_msb=program.msb,
            pc_lsb=program.lsb,
            pc_value=program.program,
            key_root=zone.key_root,
            key_low=zone.key_low,
            key_high=zone.key_high,
            min_velocity=velocity.min_velocity,
            max_velocity=velocity.max_velocity,
            velocity=velocity.send_velocity,
            use_scale_spn_format=scale_name_format == "SPN"
        )

        export_path = RecordedAudioPath(base_dir=output_dir, file_path=output_file_path + ".wav")

        self.validate_recorded_file(export_path, recorded_path_list)
        recorded_path_list.append(export_path)

    @override
    def post_process(self, config: AudioProcessConfig, recorded_path_list: List[RecordedAudioPath], processed_output_dir: str):
        logger.info("Do nothing in Dry run")
