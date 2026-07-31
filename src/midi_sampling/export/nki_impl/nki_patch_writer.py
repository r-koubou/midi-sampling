import time
from logging import getLogger
from typing import Callable

from midi_sampling.export.abstractions import (
    InstrumentModel,
    InstrumentPatchWriter,
    PatchWriteContext,
    PatchWriteOutcome,
)
from midi_sampling.export.exceptions import ExportWriteError
from midi_sampling.export.nki_impl.nki_binary import build_nki_bytes
from midi_sampling.export.nki_impl.nki_grouping import partition_groups
from midi_sampling.export.nki_impl.nki_xml import render_program
from midi_sampling.export.nki_impl.wav_info import (
    WavDataInfo,
    read_wav_data_info,
)

logger = getLogger(__name__)

FORMAT_ID = "nki"
PATCH_SUFFIX = ".nki"


class NkiPatchWriter(InstrumentPatchWriter):
    """
    Emit one KONTAKT 1 NKI program.

    KONTAKT 1 loads WAV only, so `supported_audio_formats` forces the
    export plan to WAV, and the writer reads the already-exported
    sample files to fill in the zone lengths and the header's total
    sample data size. The clock is injectable for deterministic tests
    of the header timestamp.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock if clock is not None else time.time

    @property
    def format_id(self) -> str:
        return FORMAT_ID

    @property
    def supported_audio_formats(self) -> tuple[str, ...] | None:
        return ("wav",)

    def write(self, context: PatchWriteContext) -> PatchWriteOutcome:
        instrument = context.instrument
        patch_path = context.patch_directory / f"{instrument.name}{PATCH_SUFFIX}"

        self._warn_ignored_rt_decay(instrument)

        groups, region_groups = partition_groups(instrument)
        samples: dict[str, WavDataInfo] = {
            region.sample_path: read_wav_data_info(
                context.patch_directory / region.sample_path
            )
            for region in instrument.regions
        }
        frame_counts = tuple(
            samples[region.sample_path].frame_count
            for region in instrument.regions
        )

        xml_text = render_program(
            instrument, groups, region_groups, frame_counts
        )
        data = build_nki_bytes(
            xml_text,
            sample_data_size=sum(
                info.data_size for info in samples.values()
            ),
            timestamp=int(self._clock()),
        )

        try:
            patch_path.write_bytes(data)
        except OSError as e:
            raise ExportWriteError(
                f"{patch_path}: cannot write patch file: {e}"
            ) from e

        logger.debug(
            f"Wrote {patch_path}: {len(instrument.regions)} zone(s), "
            f"{len(groups)} group(s)"
        )
        return PatchWriteOutcome(patch_path=patch_path)

    def _warn_ignored_rt_decay(self, instrument: InstrumentModel) -> None:
        tones = sorted(
            {
                region.tone_id
                for region in instrument.regions
                if region.rt_decay is not None
            }
        )
        if tones:
            logger.warning(
                f"rt_decay is not supported by KONTAKT 1 NKI and was "
                f"ignored for tone(s): {', '.join(tones)}"
            )
