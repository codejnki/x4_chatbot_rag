# 04_generate_keywords.py (Parallelized Version)

import json
import time
import concurrent.futures
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm

# --- Configuration ---
CHUNKS_PATH = "x4_wiki_chunks.json"
PROMPT_PATH = "keyword_extractor_prompt.txt"
OUTPUT_PATH = "x4_keywords.json"
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
MODEL_NAME = "local-model"

# --- Concurrency Configuration ---
# Adjust this based on how many concurrent requests your local LLM server can handle.
# Start with a lower number (e.g., 10) and increase if your system is stable.
MAX_WORKERS = 20

# --- Retry Configuration ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# --- Global Client ---
# Initialize the client once to be shared across all threads
CLIENT = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

def process_chunk(chunk):
    """
    Processes a single chunk to extract keywords.
    This function is designed to be run in a separate thread.
    """
    content = chunk.get("content", "")
    title = chunk.get("title", "Unknown")
    
    # The title itself is a valuable keyword
    extracted_keywords = {title.strip()}

    if not content.strip():
        return extracted_keywords

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
                extracted_keywords.update(sanitized)
            
            return extracted_keywords # Success

        except (json.JSONDecodeError, ValueError, Exception) as e:
            if attempt >= MAX_RETRIES - 1:
                # All retries failed, log the error and return the partial result
                with open("failed_chunks.log", "a", encoding="utf-8") as log_file:
                    log_file.write(f"--- FAILED CHUNK (Title: {title}) ---\n")
                    log_file.write(f"Error: {e}\n\n")
                return extracted_keywords
            time.sleep(RETRY_DELAY_SECONDS)
            
    return extracted_keywords


def main():
    """
    Uses a ThreadPoolExecutor to process chunks in parallel for faster keyword extraction.
    """
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunk_data = json.load(f)

    all_keywords = set()
    total_chunks = len(chunk_data)
    print(f"Found {total_chunks} chunks to process with up to {MAX_WORKERS} parallel workers...")

    # Use ThreadPoolExecutor to process chunks concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Wrap the executor.map with tqdm for a live progress bar
        results_iterator = executor.map(process_chunk, chunk_data)
        
        for keyword_set in tqdm(results_iterator, total=total_chunks, desc="Extracting keywords"):
            if keyword_set:
                all_keywords.update(keyword_set)

    # --- Save the final output ---
    print("\n--- Processing complete. Finalizing keyword list. ---")
    sorted_keywords = sorted([k for k in all_keywords if k])
    
    output_data = {
        "description": "A comprehensive list of keywords extracted from the content of all wiki chunks using an LLM.",
        "count": len(sorted_keywords),
        "keywords": sorted_keywords
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully generated {len(sorted_keywords)} unique keywords.")
    print(f"Keyword list saved to '{OUTPUT_PATH}'")


if __name__ == "__main__":
    main()