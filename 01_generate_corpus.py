# 01_generate_corpus.py

import os
import json
import re
import tiktoken
import concurrent.futures
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm
from openai import OpenAI, APIError
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Configuration ---
DATA_SOURCE_DIR = Path(r"x4-foundations-wiki")
SANITIZED_DIR = DATA_SOURCE_DIR / "hashed_pages" # The new clean directory
PATH_MAP_FILE = DATA_SOURCE_DIR / "path_map.json"
OUTPUT_FILE = "x4_wiki_corpus.json"
TARGET_FILENAME = "WebHome.html" # Retained for consistency, though not strictly needed here

# ... (LLM Config and summarize_content_in_batches function are unchanged) ...
MAX_WORKERS = 8

def process_html_file(file_path, path_map):
    """
    Processes a single HTML file from the hashed directory, using the path_map
    to reconstruct the original source path for metadata.
    """
    try:
        # Create the key to look up the original path in our map
        relative_path = Path(file_path).relative_to(SANITIZED_DIR)
        path_key = str(relative_path).replace(os.path.sep, '/')
        original_path = path_map.get(path_key)
        
        if not original_path:
            print(f"Warning: Could not find original path for {file_path}. Skipping.")
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'lxml')
        main_content = soup.find('main', id="mainContentArea")
        if not main_content: return None

        title_tag = main_content.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        body_container = main_content.find('div', id="xwikicontent")
        if not body_container: return None

        for a_tag in body_container.find_all('a'):
            a_tag.unwrap()

        body_markdown = md(str(body_container), heading_style="ATX", strip=['img'])
        full_markdown = f"# {title}\n\n{body_markdown}"
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown).strip()

        summary = summarize_content_in_batches(cleaned_markdown)
        enriched_content = f"{summary}\n\n{cleaned_markdown}"

        return {
            'source': os.path.dirname(original_path), # Use the restored original path
            'title': title,
            'content': enriched_content
        }
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None


def main():
    print("Starting Phase 1: Data Preparation (with parallel summarization)")

    try:
        with open(PATH_MAP_FILE, 'r', encoding='utf-8') as f:
            path_map = json.load(f)
    except FileNotFoundError:
        print(f"Error: Path map not found at '{PATH_MAP_FILE}'. Run 'make data' first.")
        return

    # Find all the .html files in our new clean directory structure
    target_files = list(SANITIZED_DIR.glob('**/*.html'))

    print(f"Found {len(target_files)} pages to process with {MAX_WORKERS} workers.")

    processed_docs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_file = {executor.submit(process_html_file, file_path, path_map): file_path for file_path in target_files}
        
        for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(target_files), desc="Processing & Summarizing"):
            result = future.result()
            if result:
                processed_docs.append(result)

    print(f"\nSuccessfully processed and enriched {len(processed_docs)} documents.")

    print(f"Saving the processed data to '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_docs, f, indent=2, ensure_ascii=False)

    print("\nData preparation complete!")
    print(f"Corpus saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()