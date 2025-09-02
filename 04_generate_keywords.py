# 04_generate_keywords.py (Final, Most Robust Version)

import json
import time
import re
import concurrent.futures
import hashlib
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm

# --- Configuration ---
CHUNKS_PATH = "x4_wiki_chunks.json"
PROMPT_PATH = "keyword_extractor_prompt.txt"
OUTPUT_PATH = "x4_keywords.json"
CACHE_DIR = Path(".keyword_cache")

LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
MODEL_NAME = "local-model"

# --- Concurrency ---
MAX_WORKERS = 8

# --- Retry ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# --- Globals ---
CLIENT = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

def get_chunk_hash(chunk):
    """Creates a unique and filesystem-safe identifier for a chunk."""
    identifier = f"{chunk.get('title', '')}-{chunk.get('chunk_index', 0)}"
    return hashlib.md5(identifier.encode()).hexdigest()

def extract_json_from_string(text):
    """
    Finds and extracts a JSON object or array from a string,
    attempting to repair common LLM-induced formatting errors.
    """
    text = text.strip()

    # Attempt to find the start and end of a JSON structure
    start_bracket = text.find('[')
    start_brace = text.find('{')
    
    start_index = -1
    
    # Find the first opening bracket or brace
    if start_bracket != -1 and start_brace != -1:
        start_index = min(start_bracket, start_brace)
    elif start_bracket != -1:
        start_index = start_bracket
    elif start_brace != -1:
        start_index = start_brace
    else:
        return None # No JSON structure found

    # Determine the expected closing character
    expected_closing = ']' if text[start_index] == '[' else '}'

    # Attempt to find the last closing character
    end_index = text.rfind(expected_closing)

    # --- Repair Logic ---
    # 1. If the opening bracket/brace is present but the closing one is not
    if end_index == -1:
        text += expected_closing
        end_index = len(text) - 1
        print(f"Repaired by adding a closing '{expected_closing}'.")

    # 2. Extract the potential JSON string
    json_str = text[start_index : end_index + 1]

    # 3. Attempt to parse, with a fallback for truncated arrays
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        # If it's an array that failed, try removing the last element
        if json_str.startswith('[') and ',' in json_str:
            last_comma_index = json_str.rfind(',')
            repaired_json_str = json_str[:last_comma_index] + "\n]"
            try:
                json.loads(repaired_json_str)
                print("Repaired a truncated JSON array response.")
                return repaired_json_str
            except json.JSONDecodeError:
                pass # Final repair attempt failed

    # If all else fails
    return None


def process_chunk(chunk):
    """
    Processes a single chunk, extracts keywords, and saves the result to the cache.
    """
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
                with open("failed_chunks.log", "a", encoding="utf-8") as log_file:
                    log_file.write(f"--- FAILED CHUNK (Title: {title}, Hash: {chunk_hash}) ---\n")
                    log_file.write(f"Error: {e}\nRaw LLM Output:\n{response_text}\n\n")
                cache_file.touch()
                return
            time.sleep(RETRY_DELAY_SECONDS)

def main():
    """
    Main function to generate keywords, using a cache to resume if interrupted.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)

    processed_hashes = {f.stem for f in CACHE_DIR.glob("*.json")}
    chunks_to_process = [
        chunk for chunk in all_chunks if get_chunk_hash(chunk) not in processed_hashes
    ]

    print(f"Found {len(all_chunks)} total chunks.")
    if chunks_to_process:
        print(f"{len(chunks_to_process)} chunks need processing. Starting with {MAX_WORKERS} workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_chunk, chunk) for chunk in chunks_to_process]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(chunks_to_process), desc="Generating keywords"):
                pass 
    else:
        print("All chunks have already been processed.")

    print("\n--- Consolidating all cached keywords... ---")
    all_keywords = set()
    cached_files = list(CACHE_DIR.glob("*.json"))
    for cache_file in tqdm(cached_files, desc="Loading cache"):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                if cache_file.stat().st_size == 0:
                    continue
                keywords = json.load(f)
                all_keywords.update(keywords)
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"Warning: Could not read or decode cache file {cache_file}. Skipping.")

    print("\n--- Finalizing keyword list. ---")
    sorted_keywords = sorted([k for k in all_keywords if k])
    
    output_data = {
        "description": "A comprehensive list of keywords extracted from all wiki chunks.",
        "count": len(sorted_keywords),
        "keywords": sorted_keywords
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully generated and saved {len(sorted_keywords)} unique keywords to '{OUTPUT_PATH}'.")

if __name__ == "__main__":
    main()