# 01c_get_files_to_process.py

import argparse
import logging
from pathlib import Path
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

def get_files_to_process(input_dir: Path, output_dir: Path, input_ext: str, output_ext: str):
    """
    Compares two directories and returns a list of files that need to be processed.
    """
    files_to_process = []
    for input_file in input_dir.glob(f"**/*{input_ext}"):
        relative_path = input_file.relative_to(input_dir)
        output_file = output_dir / relative_path.with_suffix(output_ext)
        if not output_file.exists() or input_file.stat().st_mtime > output_file.stat().st_mtime:
            files_to_process.append(str(relative_path).replace("\\", "/"))
    return files_to_process

def main():
    parser = argparse.ArgumentParser(description="Get a list of files to process.")
    parser.add_argument("input_dir", type=str, help="Path to the input directory.")
    parser.add_argument("output_dir", type=str, help="Path to the output directory.")
    parser.add_argument("input_ext", type=str, help="Extension of the input files.")
    parser.add_argument("output_ext", type=str, help="Extension of the output files.")

    args = parser.parse_args()

    files_to_process = get_files_to_process(Path(args.input_dir), Path(args.output_dir), args.input_ext, args.output_ext)

    for file_path in files_to_process:
        print(file_path)

if __name__ == "__main__":
    main()
