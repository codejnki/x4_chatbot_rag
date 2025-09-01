import json
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from tqdm import tqdm

# --- Configuration ---
INPUT_CHUNKS_FILE = "x4_wiki_chunks.json"
VECTOR_STORE_PATH = "faiss_index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Processing in batches is more memory-efficient and allows for a progress bar.
# A batch size of 32 or 64 is a good starting point.
BATCH_SIZE = 64

# --- Main Logic ---
def create_vector_store_with_progress():
    """
    Loads text chunks, generates embeddings in batches with a progress bar,
    and saves them to a FAISS vector store.
    """
    print("--- Starting Phase 2: Embedding and Storing ---")

    # 1. Load the processed chunks
    try:
        with open(INPUT_CHUNKS_FILE, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        print(f"Loaded {len(chunks)} chunks from '{INPUT_CHUNKS_FILE}'.")
    except FileNotFoundError:
        print(f"Error: Chunks file not found at '{INPUT_CHUNKS_FILE}'.")
        return

    # 2. Initialize the embedding model
    print(f"Loading embedding model '{MODEL_NAME}'...")
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': False}
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
    print("Embedding model loaded successfully.")

    # 3. Prepare texts and metadata
    texts = [chunk['content'] for chunk in chunks]
    metadatas = [{'source': chunk['source'], 'title': chunk['title']} for chunk in chunks]

    # 4. Create the FAISS vector store in batches
    print(f"Creating FAISS vector store from {len(texts)} texts in batches of {BATCH_SIZE}...")
    
    vector_store = None
    # This loop iterates through the texts in steps of BATCH_SIZE
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding and Indexing Chunks"):
        # Select the current batch of texts and metadatas
        batch_texts = texts[i:i + BATCH_SIZE]
        batch_metadatas = metadatas[i:i + BATCH_SIZE]
        
        if vector_store is None:
            # For the first batch, create the vector store
            vector_store = FAISS.from_texts(
                texts=batch_texts,
                embedding=embeddings,
                metadatas=batch_metadatas
            )
        else:
            # For subsequent batches, add to the existing store
            vector_store.add_texts(
                texts=batch_texts,
                metadatas=batch_metadatas
            )

    if not vector_store:
        print("Error: Vector store was not created. No chunks were processed.")
        return

    print("\nVector store created successfully.")

    # 5. Save the vector store to disk
    print(f"Saving vector store to '{VECTOR_STORE_PATH}'...")
    vector_store.save_local(VECTOR_STORE_PATH)
    print("--- Embedding and Storing complete! ---")
    print(f"Your knowledge base is now ready at '{VECTOR_STORE_PATH}'.")


if __name__ == "__main__":
    create_vector_store_with_progress()
