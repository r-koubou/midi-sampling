import os
import sys
import shutil
from logging import getLogger

from pydub import AudioSegment
from pydub.silence import detect_nonsilent

logger = getLogger(__name__)

def trim(input_path:str, output_path: str, threshold_dBFS:float=-50, min_silence_ms:int=250):
    """
    Trim silent segments from the audio file.

    Parameters
    ----------
    input_path : str
        Input audio file path (*.wav).

    output_path : str
        Output audio file path (*.wav).

    threshold_dBFS : float (default=-50)
        Silence threshold in dBFS.

    min_silence_ms : int (default=250)
        Minimum silence duration in milliseconds.
    """

    audio = AudioSegment.from_wav(input_path)
    nonsilent_ranges = detect_nonsilent(audio, min_silence_len=min_silence_ms, silence_thresh=threshold_dBFS)

    result_message = f"input={input_path}, output={output_path}, threshold_dBFS={threshold_dBFS}, min_silence_ms={min_silence_ms}"

    if nonsilent_ranges:
        start, end = nonsilent_ranges[0][0], nonsilent_ranges[-1][1]
        trimmed_audio = audio[start:end]
        trimmed_audio.export(output_path, format="wav")
    else:
        if input_path != output_path:
            shutil.copy(input_path, output_path)


def batch_trim(input_directory: str, output_directory: str, threshold_dBFS:float=-50, min_silence_ms:int=250):
    """
    Trim silent segments from all audio files in the input directory.

    Parameters
    ----------
    input_directory : str
        Input directory containing audio files (*.wav).

    output_directory : str
        Output directory to save trimmed audio files.

    threshold_dBFS : float (default=-50)
        Silence threshold in dBFS.

    min_silence_ms : int (default=250)
        Minimum silence duration in milliseconds.
    """

    os.makedirs(output_directory, exist_ok=True)

    logger.info(f"Trim Begin: input={input_directory}, output={output_directory}, threshold_dBFS={threshold_dBFS}, min_silence_ms={min_silence_ms}")

    for filename in os.listdir(input_directory):
        if filename.endswith('.wav'):
            input_path = os.path.join(input_directory, filename)
            output_path = os.path.join(output_directory, filename)
            trim(input_path, output_path, threshold_dBFS, min_silence_ms)
            logger.info(f"Trimmed: {filename}")

    logger.info(f"Trim End")

if __name__ == '__main__':
    if len(sys.argv) < 5:
        print(f"Usage: python -m {__spec__.name} <directory> <output_directory> <threshold in dBFS> <min silence in ms>")
        sys.exit(1)

    import logging
    logger.setLevel("INFO")
    logger.addHandler(logging.StreamHandler())

    args = sys.argv[1:]

    directory           = args[0]
    output_directory    = args[1]
    threshold           = float(args[2])
    min_silence         = int(args[3])
    batch_trim(directory, output_directory, threshold, min_silence)
