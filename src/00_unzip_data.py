# 00_unzip_data.py

import zipfile
import hashlib
import json
import logging
from pathlib import Path
from tqdm import tqdm
from logging_config import configure_logging

configure_logging()


logger = logging.getLogger(__name__)


# --- Configuration ---
ZIP_FILE = Path("x4-foundations-wiki.zip")
EXTRACT_ROOT_DIR = Path("x4-foundations-wiki")
SANITIZED_DIR = EXTRACT_ROOT_DIR / "hashed_pages"
PATH_MAP_FILE = EXTRACT_ROOT_DIR / "path_map.json"
HASH_FILE = EXTRACT_ROOT_DIR / "file_hashes.json"
TARGET_FILENAME = "WebHome.html"

def get_file_sha256(file_path):
    """Calculates the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def main():
    """
    Extracts only the 'WebHome.html' files from the wiki zip, renaming them
    based on a hash of their original path to create a clean, flat directory
    structure that avoids all path length issues.
    Performs an incremental unzip by comparing file hashes.
    """
    if not ZIP_FILE.exists():
        logger.error(f"Zip file not found at '{ZIP_FILE}'. Please download the wiki data.")
        return

    logger.info(f"--> Sanitizing and extracting '{ZIP_FILE}'...")
    
    SANITIZED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing path map and file hashes
    path_map = {}
    if PATH_MAP_FILE.exists():
        with open(PATH_MAP_FILE, 'r', encoding='utf-8') as f:
            path_map = json.load(f)

    file_hashes = {}
    if HASH_FILE.exists():
        with open(HASH_FILE, 'r', encoding='utf-8') as f:
            file_hashes = json.load(f)

    new_files = []
    updated_files = []
    processed_keys = set()

    with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
        file_list = [f for f in zip_ref.infolist() if f.filename.endswith(TARGET_FILENAME)]

        for member in tqdm(file_list, desc="Checking and extracting pages"):
            original_path_str = member.filename
            
            path_hash = hashlib.md5(original_path_str.encode()).hexdigest()
            
            dir1 = path_hash[0:2]
            dir2 = path_hash[2:4]
            new_filename = f"{path_hash[4:]}.html"
            
            new_path = SANITIZED_DIR / dir1 / dir2 / new_filename
            relative_new_path_key = f"{dir1}/{dir2}/{new_filename}"
            processed_keys.add(relative_new_path_key)

            # Calculate hash of the file content in the zip
            with zip_ref.open(member) as source:
                zip_file_content = source.read()
                zip_file_hash = hashlib.sha256(zip_file_content).hexdigest()

            # Compare with existing file
            if new_path.exists() and file_hashes.get(relative_new_path_key) == zip_file_hash:
                continue  # Skip if file is unchanged

            # Write new/updated file
            new_path.parent.mkdir(parents=True, exist_ok=True)
            with open(new_path, "wb") as target:
                target.write(zip_file_content)

            if relative_new_path_key not in file_hashes:
                new_files.append(relative_new_path_key)
            else:
                updated_files.append(relative_new_path_key)

            file_hashes[relative_new_path_key] = zip_file_hash
            path_map[relative_new_path_key] = original_path_str

    # Detect and handle deleted files
    deleted_keys = set(file_hashes.keys()) - processed_keys
    for key in deleted_keys:
        logger.info(f"Removing deleted file: {path_map.get(key, 'Unknown Path')}")
        path_hash = hashlib.md5(path_map.get(key, '').encode()).hexdigest()
        dir1 = path_hash[0:2]
        dir2 = path_hash[2:4]
        new_filename = f"{path_hash[4:]}.html"
        file_to_delete = SANITIZED_DIR / dir1 / dir2 / new_filename
        if file_to_delete.exists():
            file_to_delete.unlink()
        del file_hashes[key]
        del path_map[key]


    with open(PATH_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(path_map, f, indent=2)

    with open(HASH_FILE, 'w', encoding='utf-8') as f:
        json.dump(file_hashes, f, indent=2)

    logger.info(f"--> Extraction complete.")
    logger.info(f"    {len(new_files)} new files extracted.")
    logger.info(f"    {len(updated_files)} files updated.")
    logger.info(f"    {len(deleted_keys)} files deleted.")

if __name__ == "__main__":
    main()
