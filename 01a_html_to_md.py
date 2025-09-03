# 01a_html_to_md.py

import argparse
import re
import logging
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from pathlib import Path

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("console.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

# --- Configuration ---
DATA_SOURCE_DIR = Path("x4-foundations-wiki")
SANITIZED_DIR = Path(DATA_SOURCE_DIR,  "hashed_pages")
MD_PAGES_DIR = Path(DATA_SOURCE_DIR, "pages_md")

def parse_changelog_to_list(table_soup):
    """
    A specialized parser that converts the changelog HTML table
    into a nested markdown list. It handles multiple changes within
    a single list item by splitting them.
    """
    markdown_lines = []
    rows = table_soup.find_all('tr')
    
    if rows and rows[0].find('th'):
        rows = rows[1:]

    for row in rows:
        cols = row.find_all('td')
        if len(cols) == 2:
            version_cell_text = cols[0].get_text(separator=' ', strip=True)
            markdown_lines.append(f"\n* {version_cell_text}")
            
            description_cell = cols[1]
            list_items = description_cell.find_all('li')
            
            texts_to_process = []
            if list_items:
                # If proper <li> tags exist, use their text content.
                texts_to_process = [li.get_text(strip=True) for li in list_items]
            else:
                # Otherwise, use the entire cell's text.
                cell_text = description_cell.get_text(strip=True)
                if cell_text:
                    texts_to_process.append(cell_text)

            # Apply the same splitting logic to all collected text items.
            for text_item in texts_to_process:
                # Normalize all bullet-like characters to '*' for splitting
                normalized_text = text_item.replace('•', '*')
                
                # Split into individual changes
                individual_changes = normalized_text.split('*')
                
                for change in individual_changes:
                    clean_change = change.strip()
                    if clean_change:
                        markdown_lines.append(f"  * {clean_change}")
            
    return '\n'.join(markdown_lines)

def process_html_file(input_path: Path, output_path: Path):
    """
    Reads a single HTML file, extracts the title and main content, converts
    it to Markdown, and saves it to a new file.
    Uses a specialized parser for changelog pages.
    """
    try:
        with input_path.open('r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'lxml')
        main_content = soup.find('main', id="mainContentArea")
        if not main_content:
            logger.warning(f"No main content area found in {input_path}. Skipping.")
            return

        title_tag = main_content.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        body_container = main_content.find('div', id="xwikicontent")
        if not body_container:
            logger.warning(f"No body container found in {input_path}. Skipping.")
            return
            
        changelog_table = body_container.find("table")
        is_changelog = False
        if changelog_table:
            header = changelog_table.find('th')
            if header and "version / date" in header.get_text(strip=True).lower():
                is_changelog = True

        if is_changelog:
            body_markdown = parse_changelog_to_list(changelog_table)
        else:
            for a_tag in body_container.find_all('a'):
                a_tag.unwrap()
            body_markdown = md(str(body_container), heading_style="ATX", strip=['img'])

        full_markdown = f"# {title}\n{body_markdown}"
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown).strip()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_markdown)

        logger.info(f"Successfully converted {input_path} to {output_path}")

    except Exception as e:
        logger.error(f"Error processing file {input_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Convert a single HTML file to Markdown.")
    parser.add_argument("input_file", type=str, help="Path to the input HTML file relative to the sanitized pages directory.")
    
    args = parser.parse_args()
    clean_input_file = args.input_file.strip()

    input_file_path = Path(SANITIZED_DIR, clean_input_file)
    output_file_path = Path(MD_PAGES_DIR, Path(clean_input_file).with_suffix(".md"))

    if not input_file_path.exists():
        logger.error(f"Input file not found: {input_file_path}")
        return

    process_html_file(input_file_path, output_file_path)

if __name__ == "__main__":
    main()