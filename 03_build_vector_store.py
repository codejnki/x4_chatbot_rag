# 03_build_vector_store.py

import json
import logging
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from tqdm import tqdm

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
CHUNKS_FILE = "x4_all_chunks.json"
VECTOR_STORE_PATH = "faiss_index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def main():
    """
    Loads document chunks, generates embeddings using a HuggingFace model,
    and creates and saves a FAISS vector store.
    """
    logger.info("--- Starting Phase 3: Building Vector Store ---")

    try:
        with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        logger.info(f"Loaded {len(chunks_data)} document chunks from '{CHUNKS_FILE}'.")
    except FileNotFoundError:
        logger.error(f"Chunks file not found at '{CHUNKS_FILE}'. Please run 'make chunks' first.")
        return

    documents = [
        Document(
            page_content=chunk.get("content", ""),
            metadata={
                "source": chunk.get("source", "Unknown"),
                "title": chunk.get("title", "Untitled"),
                "chunk_index": chunk.get("chunk_index", 0)
            }
        ) for chunk in chunks_data
    ]

    logger.info(f"Initializing embedding model '{MODEL_NAME}'...")
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        encode_kwargs={'normalize_embeddings': True}
    )
    logger.info("Embedding model initialized successfully.")

    logger.info("Building FAISS vector store. This will take some time...")
    vector_store = FAISS.from_documents(documents, embeddings)

    logger.info("Vector store built successfully.")

    logger.info(f"Saving vector store to '{VECTOR_STORE_PATH}'...")
    vector_store.save_local(VECTOR_STORE_PATH)
    logger.info(f"Vector store saved successfully.")
    logger.info("\n--- Data pipeline complete! ---")


if __name__ == "__main__":
    main()
