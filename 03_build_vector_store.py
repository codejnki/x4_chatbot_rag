# 03_build_vector_store.py

import json
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from tqdm import tqdm

# --- Configuration ---
CHUNKS_FILE = "x4_wiki_chunks.json"
VECTOR_STORE_PATH = "faiss_index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def main():
    """
    Loads document chunks, generates embeddings using a HuggingFace model,
    and creates and saves a FAISS vector store.
    """
    print("--- Starting Phase 3: Building Vector Store ---")

    # 1. Load the pre-chunked documents
    try:
        with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        print(f"Loaded {len(chunks_data)} document chunks from '{CHUNKS_FILE}'.")
    except FileNotFoundError:
        print(f"Error: Chunks file not found at '{CHUNKS_FILE}'. Please run 'make chunks' first.")
        return

    # Convert dictionary chunks into LangChain Document objects
    # This is necessary for the FAISS vector store creation process.
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

    # 2. Initialize the embedding model
    print(f"Initializing embedding model '{MODEL_NAME}'...")
    # By specifying encode_kwargs, we ensure embeddings are normalized, which is good practice for similarity search.
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        encode_kwargs={'normalize_embeddings': True}
    )
    print("Embedding model initialized successfully.")

    # 3. Create the FAISS vector store from the documents and embeddings
    print("Building FAISS vector store. This will take some time...")
    # We'll process the documents in batches to show progress with tqdm
    vector_store = FAISS.from_documents(documents, embeddings)

    print("Vector store built successfully.")

    # 4. Save the vector store locally
    print(f"Saving vector store to '{VECTOR_STORE_PATH}'...")
    vector_store.save_local(VECTOR_STORE_PATH)
    print(f"Vector store saved successfully.")
    print("\n--- Data pipeline complete! ---")


if __name__ == "__main__":
    main()