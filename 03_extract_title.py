from bs4 import BeautifulSoup
import os

# --- Configuration ---
DATA_SOURCE_DIR = r"./x4-foundations-wiki/pages/Manual+and+Guides/How+to+dock+your+ship"
FILE_TO_PROCESS = "WebHome.html" 
# The ID of the main content area that contains everything we want.
MAIN_CONTENT_ID = "mainContentArea" 
# The ID of the specific div that holds the title h1 tag.
TITLE_CONTAINER_ID = "document-title" 

# --- Main Logic ---
def extract_title_from_html(file_path):
    """
    Parses an HTML file, finds the main content area, and extracts the document's H1 title.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        soup = BeautifulSoup(content, 'lxml')
        
        # 1. First, find the main content container to narrow our search.
        main_content = soup.find('main', id=MAIN_CONTENT_ID)

        if not main_content:
            print(f"Warning: Main content container '{MAIN_CONTENT_ID}' not found in {file_path}")
            return None
        
        # 2. Now, search for the title container *within* the main content.
        title_container = main_content.find('div', id=TITLE_CONTAINER_ID)

        if not title_container:
            print(f"Warning: Title container '{TITLE_CONTAINER_ID}' not found in {file_path}")
            return None

        # 3. Find the H1 tag inside the title container.
        h1_tag = title_container.find('h1')

        if not h1_tag:
            print(f"Warning: H1 tag not found within title container in {file_path}")
            return None
        
        # 4. Get the clean text from the H1 tag.
        return h1_tag.get_text(strip=True)

    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")
        return None


if __name__ == "__main__":
    full_path = os.path.join(DATA_SOURCE_DIR, FILE_TO_PROCESS)
    
    print(f"--- Extracting title from: {full_path} ---")
    extracted_title = extract_title_from_html(full_path)

    if extracted_title:
        print(f"\nSuccessfully Extracted Title: '{extracted_title}'")
    else:
        print("\nFailed to extract title.")

