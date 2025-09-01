from bs4 import BeautifulSoup
import os

# --- Configuration ---
# Point this to the directory where your wiki HTML files are stored.
# DATA_SOURCE_DIR = r"C:\Users\Patrick\Documents\dev\codejnki\x4_chatbot_rag\x4-foundations-wiki\pages\Manual+and+Guides\How+to+dock+your+ship" 
DATA_SOURCE_DIR = "./x4-foundations-wiki/pages/Manual+and+Guides/How+to+dock+your+ship" 
# Pick a representative file to inspect. A major faction or ship page is usually a good choice.
FILE_TO_INSPECT = "WebHome.html" 

# --- Main Logic ---
def inspect_html_file(file_path):
    """
    Loads, parses, and prints the prettified structure of a single HTML file.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return

    print(f"--- Inspecting HTML structure of: {file_path} ---")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Create a BeautifulSoup object. 'lxml' is a fast and robust parser.
        soup = BeautifulSoup(content, 'lxml')

        # Prettify the HTML to make it readable, with proper indentation.
        print(soup.prettify())

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Construct the full path to the file
    full_path = os.path.join(DATA_SOURCE_DIR, FILE_TO_INSPECT)
    inspect_html_file(full_path)