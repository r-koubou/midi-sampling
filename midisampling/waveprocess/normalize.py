import os
import sys
from pydub import AudioSegment

def normalize_across_mitiple(input_directory: str, output_directory: str, target_peak_dBFS:float =-1.0):
    """
    Normalize with respect to the highest peak of the audio file(s) in the input directory.

    Parameters
    ----------
    input_directory : str
        Input directory containing audio files (*.wav).

    output_directory : str
        Output directory to save normalized audio files.

    target_peak_dBFS : float (default=-1.0)
    """
    max_peak_dBFS = None
    audio_segments = []

    os.makedirs(output_directory, exist_ok=True)

    # 全てのファイルの最大ピークレベルを探す
    for filename in os.listdir(input_directory):
        if filename.endswith('.wav'):
            input_filepath  = os.path.join(input_directory, filename)
            output_filepath = os.path.join(output_directory, filename)
            audio = AudioSegment.from_wav(input_filepath)
            peak_dBFS = audio.max_dBFS

            if max_peak_dBFS is None or peak_dBFS > max_peak_dBFS:
                max_peak_dBFS = peak_dBFS

            audio_segments.append((audio, output_filepath))

    change_in_dBFS = target_peak_dBFS - max_peak_dBFS

    # 各ファイルに対して同じゲインを適用
    for audio, output_filepath in audio_segments:
        normalized_audio = audio.apply_gain(change_in_dBFS)
        normalized_audio.export(output_filepath, format="wav")
        print(f'Normalized {output_filepath} -> {target_peak_dBFS} dBFS (gain={change_in_dBFS:.3f} dB)')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(f"Usage: python {os.path.basename(__file__)} <directory> <output_directory> <target peak db>")
        sys.exit(1)

    args = sys.argv[1:]
    input_directory  = args[0]
    output_directory = args[1]
    target_peak_dBFS = float(args[2])

    normalize_across_mitiple(input_directory, output_directory, target_peak_dBFS)
