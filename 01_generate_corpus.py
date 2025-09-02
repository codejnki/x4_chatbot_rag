# 01_generate_corpus.py

import os
import json
import re
# ... (other imports remain the same)
from pathlib import Path

# --- Configuration ---
DATA_SOURCE_DIR = Path(r"x4-foundations-wiki") # Use Path object
PATH_MAP_FILE = DATA_SOURCE_DIR / "path_map.json" # Path to the new map file
OUTPUT_FILE = "x4_wiki_corpus.json"
# ... (rest of configuration is the same)

# --- (The summarize_content_in_batches function remains unchanged) ---

# --- Core Processing Function (Updated) ---
def process_html_file(file_path, path_map):
    """
    Processes a single HTML file, using the path_map to reconstruct the
    original source path.
    """
    try:
        # Reconstruct the original, meaningful source path from the map
        relative_path_parts = Path(file_path).relative_to(DATA_SOURCE_DIR).parts
        original_source_parts = [path_map.get(part, part) for part in relative_path_parts]
        original_source = "/".join(original_source_parts)

        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # ... (rest of the HTML parsing logic is the same) ...
        
        # --- FIX: Ensure full_markdown is defined before cleaned_markdown ---
        body_markdown = md(str(body_container), heading_style="ATX", strip=['img'])
        full_markdown = f"# {title}\n\n{body_markdown}"
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown).strip()
        # --- END FIX ---

        summary = summarize_content_in_batches(cleaned_markdown)
        enriched_content = f"{summary}\n\n{cleaned_markdown}"

        return {
            'source': os.path.dirname(original_source), # Use the reconstructed original source
            'title': title,
            'content': enriched_content
        }
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None

# --- Main Execution (Updated) ---
def main():
    print("Starting Phase 1: Data Preparation (with parallel summarization)")

    # Load the path map first
    try:
        with open(PATH_MAP_FILE, 'r', encoding='utf-8') as f:
            path_map = json.load(f)
        print(f"Loaded {len(path_map)} entries from path map.")
    except FileNotFoundError:
        print(f"Error: Path map file not found at '{PATH_MAP_FILE}'. Please run 'make data' first.")
        return

    target_files = []
    for root, _, files in os.walk(DATA_SOURCE_DIR):
        if TARGET_FILENAME in files:
            target_files.append(os.path.join(root, TARGET_FILENAME))

    if not target_files:
        print(f"Error: No files named '{TARGET_FILENAME}' found in '{DATA_SOURCE_DIR}'.")
        return

    print(f"Found {len(target_files)} pages to process with {MAX_WORKERS} workers.")

    processed_docs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Pass the path_map to each worker
        future_to_file = {executor.submit(process_html_file, file_path, path_map): file_path for file_path in target_files}
        
        for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(target_files), desc="Processing & Summarizing"):
            result = future.result()
            if result:
                processed_docs.append(result)

    # ... (rest of main function is the same) ...

if __name__ == "__main__":
    main()