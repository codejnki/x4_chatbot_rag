import os
import json
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm

# --- Configuration ---
DATA_SOURCE_DIR = r"x4-foundations-wiki"
OUTPUT_FILE = "x4_wiki_corpus.json"
TARGET_FILENAME = "WebHome.html"

MAIN_CONTENT_ID = "mainContentArea" 
BODY_CONTENT_ID = "xwikicontent" 

# --- Core Processing Function ---
def process_html_file(file_path):
    """
    Takes a file path, extracts content, cleans it by removing links while 
    keeping their text, converts to clean Markdown, and returns a dictionary.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'lxml')
        main_content = soup.find('main', id=MAIN_CONTENT_ID)
        
        if not main_content:
            return None

        title_tag = main_content.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        body_container = main_content.find('div', id=BODY_CONTENT_ID)
        if not body_container:
            return None
            
        # --- NEW STEP: Strip links but keep the text ---
        # Find all 'a' tags within the body content.
        for a_tag in body_container.find_all('a'):
            # .unwrap() removes the tag and leaves its content behind.
            a_tag.unwrap()
        
        # Now that the 'a' tags are gone, we convert the modified HTML to Markdown
        body_markdown = md(
            str(body_container), 
            heading_style="ATX", 
            strip=['img'] # We still strip images completely
        )
        
        # Combine title and body
        full_markdown = f"# {title}\n\n{body_markdown}"
        
        # Final polish: normalize excessive newlines
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown).strip()
        
        return {
            'source': os.path.basename(os.path.dirname(file_path)),
            'title': title,
            'content': cleaned_markdown
        }

    except Exception as e:
        return None

# --- Main Execution ---
def main():
    """
    Main function to find, process, and save all wiki pages.
    """
    print("Starting Phase 1: Data Preparation (with link stripping)")
    
    target_files = []
    for root, _, files in os.walk(DATA_SOURCE_DIR):
        if TARGET_FILENAME in files:
            target_files.append(os.path.join(root, TARGET_FILENAME))
    
    if not target_files:
        print(f"Error: No files named '{TARGET_FILENAME}' found in '{DATA_SOURCE_DIR}'.")
        return

    print(f"Found {len(target_files)} pages to process.")

    processed_docs = []
    for file_path in tqdm(target_files, desc="Processing HTML files"):
        result = process_html_file(file_path)
        if result:
            processed_docs.append(result)

    print(f"Successfully processed {len(processed_docs)} documents.")

    print(f"Saving the processed data to '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_docs, f, indent=2, ensure_ascii=False)
        
    print("\nData preparation complete!")
    print(f"Corpus saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
