# 00_unzip_data.py

import zipfile
import hashlib
import json
import logging
from pathlib import Path
from tqdm import tqdm

# --- Logging Configuration ---
class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("console.log"),
        TqdmLoggingHandler()
    ]
)

logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

# --- Configuration ---
ZIP_FILE = Path("x4-foundations-wiki.zip")
EXTRACT_ROOT_DIR = Path("x4-foundations-wiki")
SANITIZED_DIR = EXTRACT_ROOT_DIR / "hashed_pages"
PATH_MAP_FILE = EXTRACT_ROOT_DIR / "path_map.json"
TARGET_FILENAME = "WebHome.html"

def main():
    """
    Extracts only the 'WebHome.html' files from the wiki zip, renaming them
    based on a hash of their original path to create a clean, flat directory
    structure that avoids all path length issues.
    """
    if not ZIP_FILE.exists():
        logger.error(f"Zip file not found at '{ZIP_FILE}'. Please download the wiki data.")
        return

    logger.info(f"--> Sanitizing and extracting '{ZIP_FILE}'...")
    
    SANITIZED_DIR.mkdir(parents=True, exist_ok=True)
    
    path_map = {}

    with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
        file_list = [f for f in zip_ref.infolist() if f.filename.endswith(TARGET_FILENAME)]

        for member in tqdm(file_list, desc="Hashing and extracting pages"):
            original_path_str = member.filename
            
            path_hash = hashlib.md5(original_path_str.encode()).hexdigest()
            
            dir1 = path_hash[0:2]
            dir2 = path_hash[2:4]
            new_filename = f"{path_hash[4:]}.html"
            
            new_path = SANITIZED_DIR / dir1 / dir2 / new_filename
            
            relative_new_path_key = f"{dir1}/{dir2}/{new_filename}"
            path_map[relative_new_path_key] = original_path_str

            new_path.parent.mkdir(parents=True, exist_ok=True)
            with zip_ref.open(member) as source, open(new_path, "wb") as target:
                target.write(source.read())

    with open(PATH_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(path_map, f, indent=2)

    logger.info(f"--> Extraction complete. {len(path_map)} pages extracted to '{SANITIZED_DIR}'.")

if __name__ == "__main__":
    main()