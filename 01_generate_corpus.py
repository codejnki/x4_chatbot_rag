import os
import json
import re
import tiktoken
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm
from openai import OpenAI, APIError
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Configuration ---
DATA_SOURCE_DIR = r"x4-foundations-wiki"
OUTPUT_FILE = "x4_wiki_corpus.json"
TARGET_FILENAME = "WebHome.html"

MAIN_CONTENT_ID = "mainContentArea"
BODY_CONTENT_ID = "xwikicontent"

# --- LLM Configuration for Summarization ---
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
SUMMARIZER_PROMPT_PATH = "table_summarizer_prompt.txt"

# Context window configuration
MAX_CONTEXT_TOKENS = 6000

# Initialize the OpenAI client and tokenizer
CLIENT = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
SUMMARIZER_PROMPT_TEMPLATE = Path(SUMMARIZER_PROMPT_PATH).read_text("utf-8")
tokenizer = tiktoken.get_encoding("cl100k_base")

# --- Batching Summarization Function ---
def summarize_content_in_batches(content: str) -> str:
    """
    Splits large content into chunks, summarizes each chunk, and then consolidates
    the summaries to create a final, comprehensive summary.
    """
    content_tokens = len(tokenizer.encode(content))
    
    # If the content is small enough, summarize it directly
    if content_tokens < MAX_CONTEXT_TOKENS:
        try:
            formatted_prompt = SUMMARIZER_PROMPT_TEMPLATE.format(content=content)
            response = CLIENT.chat.completions.create(
                model="local-model",
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.2,
            )
            return response.choices[0].message.content
        except APIError as e:
            print(f"Warning: API error during direct summarization: {e}")
            return "" # Return empty string on failure
            
    # If the content is too large, split it and summarize in batches
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_CONTEXT_TOKENS,
        chunk_overlap=200,
        length_function=lambda text: len(tokenizer.encode(text)),
    )
    chunks = text_splitter.split_text(content)
    
    summaries = []
    print(f"\nContent too large ({content_tokens} tokens), splitting into {len(chunks)} batches.")
    for i, chunk in enumerate(tqdm(chunks, desc="Summarizing batches", leave=False)):
        try:
            formatted_prompt = SUMMARIZER_PROMPT_TEMPLATE.format(content=chunk)
            response = CLIENT.chat.completions.create(
                model="local-model",
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.2,
            )
            summaries.append(response.choices[0].message.content)
        except APIError as e:
            print(f"Warning: API error summarizing batch {i+1}: {e}")
            continue

    if not summaries:
        return ""

    # Consolidate the summaries if there are more than one
    if len(summaries) > 1:
        try:
            combined_summaries = "\n\n".join(summaries)
            final_prompt = f"Consolidate the following summaries into a single, coherent summary:\n\n{combined_summaries}"
            final_response = CLIENT.chat.completions.create(
                model="local-model",
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.2,
            )
            return final_response.choices[0].message.content
        except APIError as e:
            print(f"Warning: API error during final consolidation: {e}")
            return combined_summaries
    
    return summaries[0]


# --- Core Processing Function (Corrected) ---
def process_html_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'lxml')
        main_content = soup.find('main', id=MAIN_CONTENT_ID)
        if not main_content: return None

        title_tag = main_content.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        body_container = main_content.find('div', id=BODY_CONTENT_ID)
        if not body_container: return None

        for a_tag in body_container.find_all('a'):
            a_tag.unwrap()

        body_markdown = md(str(body_container), heading_style="ATX", strip=['img'])
        
        # --- THIS IS THE FIX ---
        # Combine title and body to create the full markdown content first
        full_markdown = f"# {title}\n\n{body_markdown}"
        # Then clean it
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown).strip()
        # --- END FIX ---

        # Now, pass the full, cleaned markdown to the new batching summarizer
        summary = summarize_content_in_batches(cleaned_markdown)
        
        # Combine the new summary with the original content
        enriched_content = f"{summary}\n\n{cleaned_markdown}"

        return {
            'source': os.path.basename(os.path.dirname(file_path)),
            'title': title,
            'content': enriched_content
        }
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None

# --- Main Execution ---
def main():
    print("Starting Phase 1: Data Preparation (with LLM summarization)")
    
    target_files = []
    for root, _, files in os.walk(DATA_SOURCE_DIR):
        if TARGET_FILENAME in files:
            target_files.append(os.path.join(root, TARGET_FILENAME))
    
    if not target_files:
        print(f"Error: No files named '{TARGET_FILENAME}' found in '{DATA_SOURCE_DIR}'.")
        return

    print(f"Found {len(target_files)} pages to process.")

    processed_docs = []
    for file_path in tqdm(target_files, desc="Processing & Summarizing HTML"):
        result = process_html_file(file_path)
        if result:
            processed_docs.append(result)

    print(f"Successfully processed and enriched {len(processed_docs)} documents.")

    print(f"Saving the processed data to '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_docs, f, indent=2, ensure_ascii=False)
        
    print("\nData preparation complete!")
    print(f"Corpus saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()