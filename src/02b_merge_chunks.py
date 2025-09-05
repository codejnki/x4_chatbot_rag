# 02b_merge_chunks.py

import json
import logging
from pathlib import Path
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

# --- Configuration ---
WIKI_CHUNKS_FILE = "x4_wiki_chunks.json"
CHANGELOG_CHUNKS_FILE = "x4_changelog_chunks.json"
OUTPUT_FILE = "x4_all_chunks.json"

def main():
    logger.info("--- Starting Phase 2b: Merging Chunk Files ---")

    wiki_chunks = []
    if Path(WIKI_CHUNKS_FILE).exists():
        with open(WIKI_CHUNKS_FILE, 'r', encoding='utf-8') as f:
            wiki_chunks = json.load(f)
        logger.info(f"Loaded {len(wiki_chunks)} chunks from '{WIKI_CHUNKS_FILE}'.")
    else:
        logger.warning(f"'{WIKI_CHUNKS_FILE}' not found. Continuing without it.")

    changelog_chunks = []
    if Path(CHANGELOG_CHUNKS_FILE).exists():
        with open(CHANGELOG_CHUNKS_FILE, 'r', encoding='utf-8') as f:
            changelog_chunks = json.load(f)
        logger.info(f"Loaded {len(changelog_chunks)} chunks from '{CHANGELOG_CHUNKS_FILE}'.")
    else:
        logger.warning(f"'{CHANGELOG_CHUNKS_FILE}' not found. Continuing without it.")

    all_chunks = wiki_chunks + changelog_chunks

    logger.info(f"Total combined chunks: {len(all_chunks)}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved all chunks to '{OUTPUT_FILE}'.")
    logger.info("--- Chunk Merging Complete ---")

if __name__ == "__main__":
    main()