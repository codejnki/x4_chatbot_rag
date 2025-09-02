# 04_generate_keywords.py (Resumable & Cached Version)

import json
import time
import concurrent.futures
import hashlib
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm

# --- Configuration ---
CHUNKS_PATH = "x4_wiki_chunks.json"
PROMPT_PATH = "keyword_extractor_prompt.txt"
OUTPUT_PATH = "x4_keywords.json"
CACHE_DIR = Path(".keyword_cache") # Directory to store intermediate results

LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
MODEL_NAME = "local-model"

# --- Concurrency ---
# It's better to start lower and find the sweet spot for your machine.
MAX_WORKERS = 4

# --- Retry ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# --- Globals ---
CLIENT = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

def get_chunk_hash(chunk):
    """Creates a unique and filesystem-safe identifier for a chunk."""
    # Use a combination of title and chunk index to ensure uniqueness
    identifier = f"{chunk.get('title', '')}-{chunk.get('chunk_index', 0)}"
    return hashlib.md5(identifier.encode()).hexdigest()

def process_chunk(chunk):
    """
    Processes a single chunk, extracts keywords, and saves the result to the cache.
    """
    chunk_hash = get_chunk_hash(chunk)
    cache_file = CACHE_DIR / f"{chunk_hash}.json"
    
    content = chunk.get("content", "")
    title = chunk.get("title", "Unknown")
    
    # Start with the title as a keyword
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
            cleaned_response = response_text.strip().replace("```json", "").replace("```", "").strip()

            if not cleaned_response:
                raise ValueError("LLM returned an empty response.")

            keywords_from_llm = json.loads(cleaned_response)
            
            if isinstance(keywords_from_llm, list):
                sanitized = {str(k).strip() for k in keywords_from_llm if k and isinstance(k, str)}
                base_keywords.update(sanitized)
            
            # On success, write all found keywords to the cache file and exit
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(list(base_keywords), f)
            return

        except Exception as e:
            if attempt >= MAX_RETRIES - 1:
                with open("failed_chunks.log", "a", encoding="utf-8") as log_file:
                    log_file.write(f"--- FAILED CHUNK (Title: {title}, Hash: {chunk_hash}) ---\n")
                    log_file.write(f"Error: {e}\n\n")
                # Write a blank file to mark as processed and prevent retries on next run
                cache_file.touch()
                return
            time.sleep(RETRY_DELAY_SECONDS)

def main():
    """
    Main function to generate keywords, using a cache to resume if interrupted.
    """
    # 1. Setup cache directory
    CACHE_DIR.mkdir(exist_ok=True)
    
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)

    # 2. Identify chunks that need processing
    processed_hashes = {f.stem for f in CACHE_DIR.glob("*.json")}
    chunks_to_process = [
        chunk for chunk in all_chunks if get_chunk_hash(chunk) not in processed_hashes
    ]

    print(f"Found {len(all_chunks)} total chunks.")
    if chunks_to_process:
        print(f"{len(chunks_to_process)} chunks need processing. Starting with {MAX_WORKERS} workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            list(tqdm(executor.map(process_chunk, chunks_to_process), total=len(chunks_to_process), desc="Generating keywords"))
    else:
        print("All chunks have already been processed.")

    # 3. Consolidate results from cache
    print("\n--- Consolidating all cached keywords... ---")
    all_keywords = set()
    cached_files = list(CACHE_DIR.glob("*.json"))
    for cache_file in tqdm(cached_files, desc="Loading cache"):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                keywords = json.load(f)
                all_keywords.update(keywords)
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"Warning: Could not read or decode cache file {cache_file}. Skipping.")


    # 4. Save the final output
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