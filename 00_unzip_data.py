# 00_unzip_data.py

import zipfile
import hashlib
import json
from pathlib import Path
from tqdm import tqdm

# --- Configuration ---
ZIP_FILE = Path("x4-foundations-wiki.zip")
EXTRACT_DIR = Path("x4-foundations-wiki")
PATH_MAP_FILE = EXTRACT_DIR / "path_map.json"
MAX_PATH_COMPONENT_LEN = 50 # A safe length for directory names

def sanitize_path(path_str: str, path_map: dict) -> Path:
    """
    Sanitizes a given path string. If a directory component is too long,
    it's replaced with a hash, and the mapping is stored.
    """
    parts = path_str.split('/')
    sanitized_parts = []
    for part in parts:
        if len(part) > MAX_PATH_COMPONENT_LEN:
            # Create a short, deterministic hash of the long part
            hashed_part = hashlib.md5(part.encode()).hexdigest()
            # Store the mapping from the hash back to the original
            path_map[hashed_part] = part
            sanitized_parts.append(hashed_part)
        else:
            sanitized_parts.append(part)
    return Path(*sanitized_parts)

def main():
    """
    Extracts the wiki data, sanitizing long file paths by replacing them with
    hashes and creating a JSON map to preserve the original names.
    """
    if not ZIP_FILE.exists():
        print(f"Error: Zip file not found at '{ZIP_FILE}'.")
        return

    print(f"--> Unzipping and sanitizing wiki data from '{ZIP_FILE}'...")
    
    EXTRACT_DIR.mkdir(exist_ok=True)
    path_map = {}

    with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
        file_list = zip_ref.infolist()
        for member in tqdm(file_list, desc="Sanitizing and extracting"):
            # Don't process directories themselves
            if member.is_dir():
                continue

            original_path_str = member.filename
            sanitized_path = EXTRACT_DIR / sanitize_path(original_path_str, path_map)
            
            # Ensure the parent directory for the sanitized path exists
            sanitized_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract the file to the new sanitized path
            with zip_ref.open(member) as source, open(sanitized_path, "wb") as target:
                target.write(source.read())

    # Save the map file for the next script to use
    with open(PATH_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(path_map, f, indent=2)

    print(f"--> Unzipping complete. Path map saved to '{PATH_MAP_FILE}'.")

if __name__ == "__main__":
    main()