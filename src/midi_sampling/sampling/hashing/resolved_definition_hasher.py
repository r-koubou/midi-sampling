import hashlib
import json


class ResolvedDefinitionHasher:
    """
    SHA-256 over the canonical JSON form of a resolved, normalized tone
    definition. The hash identifies the effective definition a sample set
    was recorded from, independent of YAML comments, key order, preset
    file locations and other cosmetic details.
    """

    def hash_payload(self, payload: dict) -> str:
        """
        Compute the SHA-256 hex digest of a canonical payload dictionary.

        The payload must already be normalized:
        - zones / velocity layers in canonical order
        - all time values as float
        """
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def build_payload(
        self,
        *,
        channel: int,
        bank_msb: int,
        bank_lsb: int,
        program: int,
        zones: list[dict],
        velocity_layers: list[dict],
        program_change_settle: float,
        pre_roll: float,
        note_on: float,
        release_capture: float,
        inter_sample_wait: float,
        sample_rate: int,
        audio_channels: int,
        data_format: str,
        sample_filename_template: str,
    ) -> dict:
        """
        Build the canonical hash payload for one tone.

        Excluded by design: YAML comments and formatting, preset file
        locations, output paths, timestamps, execution state, error
        information, application version and the display-only name.
        """
        return {
            "midi": {
                "channel": channel,
                "bank_msb": bank_msb,
                "bank_lsb": bank_lsb,
                "program": program,
            },
            "zones": [
                {
                    "low": zone["low"],
                    "root": zone["root"],
                    "high": zone["high"],
                }
                for zone in zones
            ],
            "velocity_layers": [
                {
                    "low": layer["low"],
                    "high": layer["high"],
                    "send": layer["send"],
                }
                for layer in velocity_layers
            ],
            "timing": {
                "program_change_settle": float(program_change_settle),
                "pre_roll": float(pre_roll),
                "note_on": float(note_on),
                "release_capture": float(release_capture),
                "inter_sample_wait": float(inter_sample_wait),
            },
            "audio": {
                "sample_rate": sample_rate,
                "channels": audio_channels,
                "data_format": data_format,
            },
            "naming": {
                "sample_filename": sample_filename_template,
            },
        }
