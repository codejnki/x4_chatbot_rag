# 02_chunk_corpus.py

import json
import logging
from pathlib import Path
from tqdm import tqdm
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


# --- Configuration ---
INPUT_DIR = Path("x4-foundations-wiki/pages_summarized")
OUTPUT_CHUNKS_FILE = "x4_wiki_chunks.json"

# --- Main Logic ---
def load_and_chunk_documents():
    """
    Loads all markdown documents from a directory, splits them using a
    "double chunk" method, and saves them to a single JSON file.
    """
    logger.info("--- Starting Phase 2: Chunking ---")
    
    if not INPUT_DIR.exists():
        logger.error(f"Input directory not found at '{INPUT_DIR}'. Please run 'make summarize' first.")
        return None

    # Define both chunking methods
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "Header 1"), ("##", "Header 2")]
    )
    character_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )

    all_chunks = []
    
    for file_path in tqdm(list(INPUT_DIR.rglob("*.md")), desc="Processing and chunking files"):
        
        # Load the content of the file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            continue

        # Extract title and source
        title = content.split('\n')[0].replace('#', '').strip() if content.startswith('#') else file_path.stem
        source = str(file_path.relative_to(INPUT_DIR)).replace("\\", "/")

        # --- Perform both types of chunking ---
        markdown_chunks = markdown_splitter.split_text(content)
        character_chunks = character_splitter.split_text(content)

        # Process and combine chunks from the Markdown splitter
        for i, chunk in enumerate(markdown_chunks):
            header_content = " ".join(chunk.metadata.values())
            combined_content = f"{header_content}\n\n{chunk.page_content}"
            all_chunks.append({
                'source': source,
                'title': title,
                'content': combined_content,
                'chunk_index': f"md-{i+1}"
            })

        # Process and combine chunks from the character splitter
        for i, chunk_content in enumerate(character_chunks):
            all_chunks.append({
                'source': source,
                'title': title,
                'content': chunk_content,
                'chunk_index': f"char-{i+1}"
            })
            
    logger.info(f"Processed {len(list(INPUT_DIR.rglob('*.md')))} documents into a total of {len(all_chunks)} chunks.")
    return all_chunks


if __name__ == "__main__":
    chunks = load_and_chunk_documents()
    
    if chunks:
        logger.info(f"\nSaving all chunks to '{OUTPUT_CHUNKS_FILE}'...")
        with open(OUTPUT_CHUNKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        logger.info("Chunking complete.")