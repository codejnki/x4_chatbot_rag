from bs4 import BeautifulSoup
from markdownify import markdownify as md
import os

# --- Configuration ---
DATA_SOURCE_DIR = r"./x4-foundations-wiki/pages/Manual+and+Guides/How+to+dock+your+ship"
FILE_TO_PROCESS = "WebHome.html" 
MAIN_CONTENT_ID = "mainContentArea" 
TITLE_CONTAINER_ID = "document-title" 
BODY_CONTENT_ID = "xwikicontent" 

# --- Main Logic ---
def convert_html_file_to_markdown(file_path):
    """
    Parses a single HTML file, extracts the title and main content,
    and converts it into a structured Markdown string.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'lxml')
        
        main_content = soup.find('main', id=MAIN_CONTENT_ID)
        if not main_content:
            return None # Skip files that don't have the main content block

        # --- Extract Title ---
        title_tag = main_content.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        # --- Extract and Convert Body ---
        body_container = main_content.find('div', id=BODY_CONTENT_ID)
        if not body_container:
            return None # Skip files that don't have a body content block
            
        # The markdownify library takes an HTML string as input.
        # We pass the body_container tag, converted back to a string.
        # heading_style="ATX" ensures headers are converted to '#' style.
        body_markdown = md(
            str(body_container), 
            heading_style="ATX",
            strip=['img'])
        
        # --- Combine and Finalize ---
        # We'll create a clean final output with the title as a main header.
        final_markdown = f"# {title}\n\n{body_markdown}"
        
        return {
            'title': title,
            'markdown_content': final_markdown
        }

    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")
        return None


if __name__ == "__main__":
    full_path = os.path.join(DATA_SOURCE_DIR, FILE_TO_PROCESS)
    
    print(f"--- Converting to Markdown: {full_path} ---")
    result = convert_html_file_to_markdown(full_path)

    if result:
        print("\n--- Converted Markdown Output ---")
        print(result['markdown_content'])
        print("\n--- End of Output ---")
    else:
        print("\nFailed to convert file.")
