# 12_generate_keywords_from_content.py (Corrected with max_tokens)

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

def main():
    """
    Uses an LLM to extract a comprehensive list of keywords/entities from the
    pre-chunked wiki data. Now explicitly sets max_tokens to prevent output truncation.
    """
    # --- 1. Initialization ---
    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
    
    chunks_file = Path(CHUNKS_PATH)
    prompt_file = Path(PROMPT_PATH)
    
    if not chunks_file.exists() or not prompt_file.exists():
        print(f"Error: Make sure '{CHUNKS_PATH}' and '{PROMPT_PATH}' exist.")
        return

    print("Loading pre-chunked data and prompt...")
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunk_data = json.load(f)
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    all_keywords = set()
    total_chunks = len(chunk_data)
    print(f"Found {total_chunks} chunks to process. This will take a while...")

    # --- 2. Main Processing Loop ---
    for i, chunk in enumerate(chunk_data):
        content = chunk.get("content", "")
        title = chunk.get("title", f"chunk_{i}")
        
        print(f"--- Processing chunk {i+1}/{total_chunks} (from doc: {title}) ---")
        
        all_keywords.add(title.strip())

        if not content.strip():
            print("Skipping due to empty content.")
            continue
        
        formatted_prompt = prompt_template.format(content=content)
        
        try:
            # --- THIS IS THE UPDATED SECTION ---
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.0,
                max_tokens=4096  # Explicitly request a larger output buffer
            )
            # ------------------------------------
            
            response_text = response.choices[0].message.content
            cleaned_response = response_text.strip().replace("```json", "").replace("```", "").strip()
            extracted_keywords = json.loads(cleaned_response)
            
            if isinstance(extracted_keywords, list):
                sanitized = {str(k).strip() for k in extracted_keywords if k and isinstance(k, str)}
                print(f"Extracted {len(sanitized)} new keywords from chunk.")
                all_keywords.update(sanitized)
            else:
                print("Warning: LLM did not return a list.")

        except json.JSONDecodeError:
            print(f"Error: Failed to decode JSON from LLM response for chunk.")
            print(f"LLM Raw Response:\n{response_text[:200]}...")
        except Exception as e:
            print(f"An unexpected error occurred for chunk: {e}")

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
