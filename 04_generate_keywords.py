# 12_generate_keywords_from_content.py (Final Corrected Version)

import json
import time
from pathlib import Path
from openai import OpenAI

# --- Configuration ---
CHUNKS_PATH = "x4_wiki_chunks.json" 
PROMPT_PATH = "keyword_extractor_prompt.txt"
OUTPUT_PATH = "x4_keywords.json"
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
MODEL_NAME = "local-model" 
# --- Retry Configuration ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

def main():
    """
    Uses an LLM to extract keywords from pre-chunked data.
    Relies on a robust retry mechanism to handle probabilistic failures.
    """
    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
    
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunk_data = json.load(f)
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    all_keywords = set()
    total_chunks = len(chunk_data)
    print(f"Found {total_chunks} chunks to process...")

    for i, chunk in enumerate(chunk_data):
        content = chunk.get("content", "")
        title = chunk.get("title", f"chunk_{i}")
        
        print(f"--- Processing chunk {i+1}/{total_chunks} (from doc: {title}) ---")
        
        all_keywords.add(title.strip())
        if not content.strip():
            print("Skipping due to empty content.")
            continue
        
        formatted_prompt = prompt_template.format(content=content)
        
        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": formatted_prompt}],
                    temperature=0.0,
                    max_tokens=4096,
                )
                
                response_text = response.choices[0].message.content
                cleaned_response = response_text.strip().replace("```json", "").replace("```", "").strip()

                # --- NEW: Explicit check for empty response ---
                if not cleaned_response:
                    # This raises an error that our except block will catch, triggering a retry.
                    raise ValueError("LLM returned an empty response.")

                extracted_keywords = json.loads(cleaned_response)
                
                if isinstance(extracted_keywords, list):
                    sanitized = {str(k).strip() for k in extracted_keywords if k and isinstance(k, str)}
                    print(f"Extracted {len(sanitized)} new keywords from chunk.")
                    all_keywords.update(sanitized)
                else:
                    print("Warning: LLM did not return a list.")
                
                break 
            
            except (json.JSONDecodeError, ValueError, Exception) as e:
                print(f"An error occurred on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES - 1:
                    print(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    print(f"All retries failed for chunk {i+1}. Skipping.")
                    with open("failed_chunks.log", "a", encoding="utf-8") as log_file:
                        log_file.write(f"--- FAILED CHUNK {i+1} (Title: {title}) ---\n")
                        log_file.write(content + "\n\n")

    # --- 3. Save the final output ---
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
