# 00_unzip_data.py

import zipfile
import hashlib
import json
from pathlib import Path
from tqdm import tqdm

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
        print(f"Error: Zip file not found at '{ZIP_FILE}'. Please download the wiki data.")
        return

    print(f"--> Sanitizing and extracting '{ZIP_FILE}'...")
    
    # --- THIS IS THE FIX ---
    # The 'parents=True' argument ensures that the parent directory
    # (x4-foundations-wiki) is created if it doesn't exist.
    SANITIZED_DIR.mkdir(parents=True, exist_ok=True)
    # --- END FIX ---
    
    path_map = {}

    with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
        # Find only the content pages we care about
        file_list = [f for f in zip_ref.infolist() if f.filename.endswith(TARGET_FILENAME)]

        for member in tqdm(file_list, desc="Hashing and extracting pages"):
            original_path_str = member.filename
            
            # Create a unique and deterministic ID from the original path
            path_hash = hashlib.md5(original_path_str.encode()).hexdigest()
            
            # Create a 2-level nested directory to avoid too many files in one folder
            dir1 = path_hash[0:2]
            dir2 = path_hash[2:4]
            new_filename = f"{path_hash[4:]}.html"
            
            new_path = SANITIZED_DIR / dir1 / dir2 / new_filename
            
            relative_new_path_key = f"{dir1}/{dir2}/{new_filename}"
            path_map[relative_new_path_key] = original_path_str

            # Extract the file to the new sanitized path
            new_path.parent.mkdir(parents=True, exist_ok=True)
            with zip_ref.open(member) as source, open(new_path, "wb") as target:
                target.write(source.read())

    # Save the map file for the next script to use
    with open(PATH_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(path_map, f, indent=2)

    print(f"--> Extraction complete. {len(path_map)} pages extracted to '{SANITIZED_DIR}'.")

if __name__ == "__main__":
    main()