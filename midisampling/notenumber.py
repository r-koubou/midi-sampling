from typing import Dict

# middle C
#
# [e.g.]
#
# SPN (Scientific pitch notation)
#   Note No 60 = C4
#
# Yamaha
#   Note No 60 = C3

_notenumber_scale_table: Dict[int, str] = {}
_scale_notenumber_table: Dict[str, int] = {}
_notenumber_scale_yamaha_table: Dict[int, str] = {}
_scale_notenumber_yamaha_table: Dict[str, int] = {}

_scales = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Create tables
for x in range(128):
    def create_table_impl(n: int, octave_begin: int, dest_nn_sc: dict, dest_sc_nn: dict) -> None:
        note      = n % 12
        octave    = n // 12 + octave_begin
        note_name = f"{_scales[note]}{octave}"
        dest_nn_sc[n] = note_name
        dest_sc_nn[note_name] = n

    def create_table(n: int) -> None:
        create_table_impl(n, -1, _notenumber_scale_table, _scale_notenumber_table)

    def create_table_yamaha(n: int) -> None:
        create_table_impl(n, -2, _notenumber_scale_yamaha_table, _scale_notenumber_yamaha_table)

    create_table(x)
    create_table_yamaha(x)


def as_scalename(note_number: int, spn_format: bool = False) -> str:
    """
    Convert note number to scale name ('C-1', 'C#-1' etc.).

    Parameters
    ----------
    note_number : int
        Note number (0-127).

    spn_format : bool, optional
        default: False
        If True, return in Scientific pitch notation format (note number 60 = 'C4').
        If False, return in aka Yamaha format (note number 60 = 'C3').
    """
    if spn_format:
        return _notenumber_scale_table[note_number]
    else:
        return _notenumber_scale_yamaha_table[note_number]

def as_notenumber(scalename: str, spn_format: bool = False) -> int:
    """
    Convert scale name ('C-1', 'C#-1' etc.) to note number.

    Parameters
    ----------
    scalename : str
        Scale name ('C-1', 'C#-1' etc.).

    spn_format : bool, optional
        default: False
        If True, return in Scientific pitch notation format ('C4' = note number 60).
        If False, return in aka Yamaha format ('C3' = note number 60).
    """
    if spn_format:
        return _scale_notenumber_table[scalename]
    else:
        return _scale_notenumber_yamaha_table[scalename]
