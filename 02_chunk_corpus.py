import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Configuration ---
INPUT_CORPUS_FILE = "x4_wiki_corpus.json"
OUTPUT_CHUNKS_FILE = "x4_wiki_chunks.json"

# Aim for chunks around 1000 characters, a good general-purpose size.
CHUNK_SIZE = 1000 
# Overlap helps maintain context between chunks.
CHUNK_OVERLAP = 200

# --- Main Logic ---
def load_and_chunk_documents():
    """
    Loads the processed JSON corpus and splits the documents into
    manageable chunks for embedding.
    """
    print("--- Starting Phase 2: Chunking ---")
    
    # 1. Load the corpus
    try:
        with open(INPUT_CORPUS_FILE, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        print(f"Loaded {len(documents)} documents from '{INPUT_CORPUS_FILE}'.")
    except FileNotFoundError:
        print(f"Error: Corpus file not found at '{INPUT_CORPUS_FILE}'.")
        return None

    # 2. Initialize the text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", " ", ""] 
    )

    # 3. Process each document and create chunks
    all_chunks = []
    for doc in documents:
        chunks = text_splitter.split_text(doc['content'])
        for i, chunk_text in enumerate(chunks):
            all_chunks.append({
                'source': doc['source'],
                'title': doc['title'],
                'content': chunk_text,
                'chunk_index': i + 1 
            })
            
    print(f"Split the documents into a total of {len(all_chunks)} chunks.")
    return all_chunks


if __name__ == "__main__":
    chunks = load_and_chunk_documents()
    
    if chunks:
        # Inspect the first 3 chunks to see the result.
        print("\n--- Example Chunks ---")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n--- Chunk {i+1} ---")
            print(f"Source: {chunk['source']}")
            print(f"Title: {chunk['title']}")
            print(f"Content Length: {len(chunk['content'])}")
            print("Content:")
            print(chunk['content'])
        
        print(f"\nSaving all chunks to '{OUTPUT_CHUNKS_FILE}' for inspection...")
        with open(OUTPUT_CHUNKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        print("Chunking complete.")
