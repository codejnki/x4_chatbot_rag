# 01d_process_changelogs.py

import json
import logging
import re
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
INPUT_DIR = Path("x4-foundations-wiki/pages_md")
OUTPUT_FILE = "x4_changelog_chunks.json"
CHANGELOG_KEYWORDS = ["changelog", "patch history"]

def is_changelog_file(file_path: Path) -> bool:
    """
    Determines if a file is a changelog file based on its filename and content.
    """
    # Check filename first for a quick match
    for keyword in CHANGELOG_KEYWORDS:
        if keyword in file_path.name.lower():
            return True
            
    # If not in filename, check content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().lower()
            if any(keyword in content for keyword in CHANGELOG_KEYWORDS):
                return True
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        
    return False

def parse_changelog_file(file_path: Path) -> list:
    """
    Parses a cleaned changelog markdown file and creates a list of
    structured chunk dictionaries.
    """
    chunks = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_version_info = ""
        source_file = str(file_path.relative_to(INPUT_DIR)).replace("\\", "/")
        title = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for the main title of the page
            if line.startswith('# '):
                title = line.lstrip('# ').strip()
                continue

            # Top-level list items are versions/dates
            if line.startswith('* '):
                current_version_info = line.lstrip('* ').strip()
            # Nested list items are the specific changes
            elif line.startswith('  * '):
                description = line.lstrip('  * ').strip()
                
                # Categorize the change
                category = "General"
                if "new feature:" in description.lower():
                    category = "New Feature"
                elif description.lower().startswith("added"):
                    category = "Added"
                elif description.lower().startswith("improved"):
                    category = "Improved"
                elif description.lower().startswith("changed"):
                     category = "Changed"
                elif description.lower().startswith("removed"):
                    category = "Removed"
                elif description.lower().startswith("fixed"):
                    category = "Fixed"

                # Create the final chunk
                chunks.append({
                    "source": source_file,
                    "title": title,
                    "version_info": current_version_info,
                    "category": category,
                    "content": description,
                    "chunk_index": len(chunks) + 1
                })

    except Exception as e:
        logger.error(f"Error parsing file {file_path}: {e}")
        
    return chunks

def main():
    """
    Identifies changelog files, parses them, and saves the structured data.
    """
    logger.info("--- Starting Dedicated Changelog Processing ---")

    if not INPUT_DIR.exists():
        logger.error(f"Input directory not found at '{INPUT_DIR}'.")
        return

    # Identify potential changelog files
    changelog_files = [
        f for f in tqdm(list(INPUT_DIR.rglob("*.md")), desc="Identifying changelog files") 
        if is_changelog_file(f)
    ]
    logger.info(f"Found {len(changelog_files)} potential changelog files.")

    all_chunks = []
    for file_path in tqdm(changelog_files, desc="Parsing changelog files"):
        all_chunks.extend(parse_changelog_file(file_path))

    logger.info(f"Extracted a total of {len(all_chunks)} changelog entry chunks.")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved structured changelog chunks to '{OUTPUT_FILE}'.")
    logger.info("--- Changelog Processing Complete ---")

if __name__ == "__main__":
    main()