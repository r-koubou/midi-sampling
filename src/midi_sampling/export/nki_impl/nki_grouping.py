from dataclasses import dataclass

from midi_sampling.export.abstractions import InstrumentModel

DEFAULT_GROUP_NAME = "default"


@dataclass(frozen=True)
class KontaktGroup:
    """
    One NiSS_Group of the generated program. `voice_group` is the index
    of the VoiceGroup entry in the program's Polyphony section (None =
    the instrument default pool), assigned as 1 + the 0-based exclusive
    group ordinal because index 0 is the built-in default VoiceGroup.
    """
    index: int
    name: str
    voice_group: int | None
    release_trigger: bool


def partition_groups(
    instrument: InstrumentModel,
) -> tuple[tuple[KontaktGroup, ...], tuple[int, ...]]:
    """
    Split the regions into KONTAKT groups keyed by (exclusive group,
    release tone). Group 0 is always the `default` group, even when no
    region lands in it; further groups are appended in order of first
    appearance. Returns the groups and, parallel to the regions, the
    group index of each region.

    A release region's tone identifies its release_triggers definition
    (the instrument definition rejects a tone that `plays` twice), so
    release ordinals are assigned per distinct release tone.
    """
    groups: list[KontaktGroup] = [
        KontaktGroup(
            index=0,
            name=DEFAULT_GROUP_NAME,
            voice_group=None,
            release_trigger=False,
        )
    ]
    group_indices: dict[tuple[int | None, str | None], int] = {
        (None, None): 0
    }
    release_ordinals: dict[str, int] = {}
    region_groups: list[int] = []

    for region in instrument.regions:
        release_tone = region.tone_id if region.trigger == "release" else None
        key = (region.exclusive_group, release_tone)

        if release_tone is not None and release_tone not in release_ordinals:
            release_ordinals[release_tone] = len(release_ordinals)

        index = group_indices.get(key)
        if index is None:
            index = len(groups)
            groups.append(
                KontaktGroup(
                    index=index,
                    name=_group_name(
                        region.exclusive_group,
                        release_ordinals.get(release_tone)
                        if release_tone is not None
                        else None,
                    ),
                    voice_group=region.exclusive_group,
                    release_trigger=release_tone is not None,
                )
            )
            group_indices[key] = index
        region_groups.append(index)

    return tuple(groups), tuple(region_groups)


def _group_name(
    exclusive_group: int | None, release_ordinal: int | None
) -> str:
    # Exclusive group numbers are 1-based; the names use 0-based ordinals.
    parts = []
    if exclusive_group is not None:
        parts.append(f"exec_{exclusive_group - 1:02d}")
    if release_ordinal is not None:
        parts.append(f"release_{release_ordinal:02d}")
    return "_".join(parts)
