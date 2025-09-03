# 02_chunk_corpus.py

import json
import logging
from tqdm import tqdm
from langchain_text_splitters import MarkdownHeaderTextSplitter

# --- Logging Configuration ---
class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("console.log"),
        TqdmLoggingHandler()
    ]
)

logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

# --- Configuration ---
INPUT_CORPUS_FILE = "x4_wiki_corpus.json"
OUTPUT_CHUNKS_FILE = "x4_wiki_chunks.json"

# --- Main Logic ---
def load_and_chunk_documents():
    """
    Loads the processed JSON corpus and splits the documents into
    manageable chunks for embedding based on Markdown headers.
    """
    logger.info("--- Starting Phase 2: Chunking ---")
    
    try:
        with open(INPUT_CORPUS_FILE, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        logger.info(f"Loaded {len(documents)} documents from '{INPUT_CORPUS_FILE}'.")
    except FileNotFoundError:
        logger.error(f"Corpus file not found at '{INPUT_CORPUS_FILE}'.")
        return None

    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    all_chunks = []
    for doc in tqdm(documents, desc="Chunking documents"):
        chunks = markdown_splitter.split_text(doc['content'])
        for i, chunk in enumerate(chunks):
            header_content = " ".join(chunk.metadata.values())
            combined_content = f"{header_content}\n\n{chunk.page_content}"

            all_chunks.append({
                'source': doc['source'],
                'title': doc['title'],
                'content': combined_content,
                'chunk_index': i + 1 
            })
            
    logger.info(f"Split the documents into a total of {len(all_chunks)} chunks.")
    return all_chunks


if __name__ == "__main__":
    chunks = load_and_chunk_documents()
    
    if chunks:
        logger.info(f"\nSaving all chunks to '{OUTPUT_CHUNKS_FILE}'...")
        with open(OUTPUT_CHUNKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        logger.info("Chunking complete.")
