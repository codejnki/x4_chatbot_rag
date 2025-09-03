# 01a_html_to_md.py

import argparse
import re
import logging
import os
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
SANITIZED_DIR = DATA_SOURCE_DIR / "hashed_pages"
MD_PAGES_DIR = DATA_SOURCE_DIR / "pages_md"

def process_html_file(input_path: Path, output_path: Path):
    """
    Reads a single HTML file, extracts the title and main content, converts
    it to Markdown, and saves it to a new file.
    """
    try:
        logger.info(f"imput_path: {input_path}")
        logger.info(f"output_path: {output_path}")
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

        for a_tag in body_container.find_all('a'):
            a_tag.unwrap()

        body_markdown = md(str(body_container), heading_style="ATX", strip=['img'])
        full_markdown = f"# {title}\n\n{body_markdown}"
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

    # input_file_path = SANITIZED_DIR / args.input_file
    # output_file_path = MD_PAGES_DIR / Path(args.input_file).with_suffix(".md")

    input_file_path = Path(os.getcwd(), SANITIZED_DIR, args.input_file.replace("\\\\", "\\"))
    output_file_path = Path(os.getcwd(),MD_PAGES_DIR, Path(args.input_file).with_suffix(".md"))

    if not input_file_path.exists():
        logger.error(f"Input file not found: {input_file_path}")
        return

    process_html_file(input_file_path, output_file_path)

if __name__ == "__main__":
    main()
