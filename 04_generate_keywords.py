# 04_generate_keywords.py

import json
import time
import re
import concurrent.futures
import hashlib
import logging
from pathlib import Path
from openai import OpenAI
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
CHUNKS_PATH = "x4_all_chunks.json"
PROMPT_PATH = "prompts/keyword_extractor_prompt.txt"
OUTPUT_PATH = "x4_keywords.json"
CACHE_DIR = Path(".keyword_cache")

LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
MODEL_NAME = "local-model"

MAX_WORKERS = 8
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# --- Globals ---
CLIENT = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

def get_chunk_hash(chunk):
    identifier = f"{chunk.get('title', '')}-{chunk.get('chunk_index', 0)}"
    return hashlib.md5(identifier.encode()).hexdigest()

def extract_json_from_string(text):
    text = text.strip()
    start_bracket = text.find('[')
    start_brace = text.find('{')
    start_index = -1
    
    if start_bracket != -1 and start_brace != -1:
        start_index = min(start_bracket, start_brace)
    elif start_bracket != -1:
        start_index = start_bracket
    elif start_brace != -1:
        start_index = start_brace
    else:
        return None

    expected_closing = ']' if text[start_index] == '[' else '}'
    end_index = text.rfind(expected_closing)

    if end_index == -1:
        text += expected_closing
        end_index = len(text) - 1
        logger.info(f"Repaired by adding a closing '{expected_closing}'.")

    json_str = text[start_index : end_index + 1]

    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        if json_str.startswith('[') and ',' in json_str:
            last_comma_index = json_str.rfind(',')
            repaired_json_str = json_str[:last_comma_index] + "\n]"
            try:
                json.loads(repaired_json_str)
                logger.info("Repaired a truncated JSON array response.")
                return repaired_json_str
            except json.JSONDecodeError:
                pass
    return None

def process_chunk(chunk):
    chunk_hash = get_chunk_hash(chunk)
    cache_file = CACHE_DIR / f"{chunk_hash}.json"
    content = chunk.get("content", "")
    title = chunk.get("title", "Unknown")
    base_keywords = {title.strip()}

    if not content.strip():
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(list(base_keywords), f)
        return

    formatted_prompt = PROMPT_TEMPLATE.format(content=content)

    for attempt in range(MAX_RETRIES):
        try:
            response = CLIENT.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.0,
                max_tokens=4096,
            )
            response_text = response.choices[0].message.content
            json_str = extract_json_from_string(response_text)
            if not json_str:
                raise ValueError("No valid JSON array found in the LLM response.")
            keywords_from_llm = json.loads(json_str)
            if isinstance(keywords_from_llm, list):
                sanitized = {str(k).strip() for k in keywords_from_llm if k and isinstance(k, str)}
                base_keywords.update(sanitized)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(list(base_keywords), f)
            return
        except Exception as e:
            if attempt >= MAX_RETRIES - 1:
                logger.error(f"Failed to process chunk (Title: {title}, Hash: {chunk_hash}). Error: {e}. Raw LLM Output: {response_text}")
                cache_file.touch() # Create empty file to mark as processed
                return
            time.sleep(RETRY_DELAY_SECONDS)

def main():
    logger.info("--- Starting Phase 4: Generating Keywords ---")
    CACHE_DIR.mkdir(exist_ok=True)
    
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)

    processed_hashes = {f.stem for f in CACHE_DIR.glob("*.json")}
    chunks_to_process = [chunk for chunk in all_chunks if get_chunk_hash(chunk) not in processed_hashes]

    logger.info(f"Found {len(all_chunks)} total chunks.")
    if chunks_to_process:
        logger.info(f"{len(chunks_to_process)} chunks need processing. Starting with {MAX_WORKERS} workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_chunk, chunk) for chunk in chunks_to_process]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(chunks_to_process), desc="Generating keywords"):
                pass 
    else:
        logger.info("All chunks have already been processed.")

    logger.info("--- Consolidating all cached keywords... ---")
    all_keywords = set()
    cached_files = list(CACHE_DIR.glob("*.json"))
    for cache_file in tqdm(cached_files, desc="Loading cache"):
        try:
            if cache_file.stat().st_size == 0:
                continue
            with open(cache_file, "r", encoding="utf-8") as f:
                keywords = json.load(f)
                all_keywords.update(keywords)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(f"Could not read or decode cache file {cache_file}. Skipping.")

    logger.info("--- Finalizing keyword list. ---")
    sorted_keywords = sorted([k for k in all_keywords if k])
    
    output_data = {
        "description": "A comprehensive list of keywords extracted from all wiki chunks.",
        "count": len(sorted_keywords),
        "keywords": sorted_keywords
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"Successfully generated and saved {len(sorted_keywords)} unique keywords to '{OUTPUT_PATH}'.")

if __name__ == "__main__":
    main()
