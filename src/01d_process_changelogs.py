# 01d_process_changelogs.py

import json
import logging
import time
import concurrent.futures
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm
from markdown_it import MarkdownIt
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


# --- Configuration ---
INPUT_DIR = Path("x4-foundations-wiki/pages_md")
OUTPUT_FILE = "x4_changelog_chunks.json"
PROMPT_PATH = "prompts/changelog_analyzer_prompt.txt"
CHANGELOG_KEYWORDS = ["changelog", "patch history"]

LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
MODEL_NAME = "local-model"

MAX_WORKERS = 4
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# --- Globals ---
CLIENT = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()
MD_PARSER = MarkdownIt()

def is_changelog_file(file_path: Path) -> bool:
    for keyword in CHANGELOG_KEYWORDS:
        if keyword in file_path.name.lower():
            return True
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if any(keyword in f.read(200).lower() for keyword in CHANGELOG_KEYWORDS):
                return True
    except Exception:
        pass
    return False

def parse_raw_entries(file_path: Path) -> list:
    entries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tokens = MD_PARSER.parse(content)
        
        title = ""
        current_version = ""
        in_top_level_list = False
        in_nested_list = False

        for i, token in enumerate(tokens):
            if token.type == 'heading_open' and token.tag == 'h1':
                title = tokens[i+1].content.strip()
            elif token.type == 'bullet_list_open':
                if not in_top_level_list:
                    in_top_level_list = True
                else:
                    in_nested_list = True
            elif token.type == 'bullet_list_close':
                if in_nested_list:
                    in_nested_list = False
                else:
                    in_top_level_list = False
            elif token.type == 'list_item_open':
                item_content = tokens[i+2].content.strip()
                if in_top_level_list and not in_nested_list:
                    current_version = item_content
                elif in_nested_list and current_version:
                    entries.append({
                        "source": str(file_path.relative_to(INPUT_DIR)).replace("\\", "/"),
                        "title": title,
                        "version_info": current_version,
                        "original_entry": item_content
                    })
    except Exception as e:
        logger.error(f"Error parsing raw entries from {file_path}: {e}")
    return entries

def process_entry_with_llm(entry_data):
    formatted_prompt = PROMPT_TEMPLATE.format(
        version_info=entry_data["version_info"],
        entry=entry_data["original_entry"]
    )
    llm_output = ""
    for attempt in range(MAX_RETRIES):
        try:
            response = CLIENT.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.1,
            )
            llm_output = response.choices[0].message.content.strip()

            # --- New Parsing Logic ---
            parsed_data = {}
            lines = llm_output.split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    parsed_data[key.strip().lower()] = value.strip()
            
            if 'category' not in parsed_data or 'summary' not in parsed_data:
                 raise ValueError("LLM output did not contain both 'category' and 'summary' keys.")

            return {
                "source": entry_data["source"],
                "title": entry_data["title"],
                "version_info": entry_data["version_info"],
                "category": parsed_data.get("category", "General"),
                "content": parsed_data.get("summary", entry_data["original_entry"]),
                "chunk_index": 0 # Placeholder
            }
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for '{entry_data['original_entry'][:50]}...': {e}. Raw LLM Output: '{llm_output}'")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Final failure processing entry after {MAX_RETRIES} attempts.")
                return None

def main():
    logger.info("--- Starting LLM-Powered Changelog Processing ---")

    if not INPUT_DIR.exists():
        logger.error(f"Input directory not found at '{INPUT_DIR}'.")
        return

    changelog_files = [f for f in INPUT_DIR.rglob("*.md") if is_changelog_file(f)]
    logger.info(f"Found {len(changelog_files)} potential changelog files.")

    raw_entries = []
    for file_path in tqdm(changelog_files, desc="Parsing raw entries"):
        raw_entries.extend(parse_raw_entries(file_path))
    logger.info(f"Found {len(raw_entries)} raw changelog entries to process.")

    if not raw_entries:
        logger.info("No entries to process. Exiting.")
        return

    processed_chunks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_entry_with_llm, entry) for entry in raw_entries]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(raw_entries), desc="Processing entries with LLM"):
            result = future.result()
            if result:
                processed_chunks.append(result)
    
    # Assign final chunk indices
    for i, chunk in enumerate(processed_chunks):
        chunk["chunk_index"] = i + 1

    logger.info(f"Successfully processed {len(processed_chunks)} changelog entries.")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_chunks, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved structured changelog chunks to '{OUTPUT_FILE}'.")
    logger.info("--- Changelog Processing Complete ---")

if __name__ == "__main__":
    main()