from bs4 import BeautifulSoup
import os

# --- Configuration ---
DATA_SOURCE_DIR = r"./x4-foundations-wiki/pages/Manual+and+Guides/How+to+dock+your+ship"
FILE_TO_PROCESS = "WebHome.html" 
# The ID of the main content area that contains everything we want.
MAIN_CONTENT_ID = "mainContentArea" 
# The ID of the div containing the article's body.
BODY_CONTENT_ID = "xwikicontent" 

# --- Main Logic ---
def extract_body_from_html(file_path):
    """
    Parses an HTML file, finds the main content area, and extracts the body text.
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
        
        # 2. Now, search for the body content container *within* the main content.
        body_container = main_content.find('div', id=BODY_CONTENT_ID)

        if not body_container:
            print(f"Warning: Body content container '{BODY_CONTENT_ID}' not found in {file_path}")
            return None

        # 3. Get all the text from within this div.
        #    - separator=' ' ensures that text from adjacent tags (like a </p><p>) has a space.
        #    - strip=True removes leading/trailing whitespace from each text block before joining.
        text = body_container.get_text(separator=' ', strip=True)
        
        return text

    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")
        return None


if __name__ == "__main__":
    full_path = os.path.join(DATA_SOURCE_DIR, FILE_TO_PROCESS)
    
    print(f"--- Extracting body content from: {full_path} ---")
    extracted_body = extract_body_from_html(full_path)

    if extracted_body:
        print("\n--- Extracted Body ---")
        print(extracted_body)
        print("\n--- End of Body ---")
    else:
        print("\nFailed to extract body content.")
