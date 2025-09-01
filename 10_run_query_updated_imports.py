# --- Final, Modernized Imports ---
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
# Use the OpenAI library to connect to the OpenAI-compatible server
from langchain_openai import ChatOpenAI

# --- Configuration ---
VECTOR_STORE_PATH = "faiss_index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# The base URL for LM Studio's OpenAI-compatible server
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LLM_MODEL_NAME = "meta-llama-3-8b-instruct" # This is ignored by LM Studio but good practice to set

# --- Main Logic ---
def main():
    """
    Loads the vector store and the LLM, then runs a RAG query.
    """
    print("--- Starting Phase 3: Retrieval and Generation ---")

    # 1. Load the existing vector store and embedding model
    print("Loading vector store and embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    vector_store = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever()
    print("Vector store loaded successfully.")

    # 2. Initialize the LLM using ChatOpenAI, pointing to our local server
    print(f"Initializing LLM from server at '{LM_STUDIO_BASE_URL}'...")
    llm = ChatOpenAI(
        model=LLM_MODEL_NAME,
        base_url=LM_STUDIO_BASE_URL,
        api_key="not-needed" # API key is required but not used by LM Studio
    )
    print("LLM initialized.")

    # 3. Define the RAG prompt template
    template = """
    You are an expert assistant for the game X4 Foundations.
    Use the following retrieved context from the game's wiki to answer the user's question.
    If you don't know the answer from the provided context, just say that you don't know.
    Keep your answer concise and helpful.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    prompt = ChatPromptTemplate.from_template(template)

    # 4. Create the RAG chain
    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # 5. Ask a question
    print("\n--- Running Query ---")
    question = "How do I dock my ship?"
    print(f"Question: {question}")
    
    response = chain.invoke(question)
    
    print("\n--- LLM Response ---")
    print(response)
    print("\n--- RAG process complete ---")

if __name__ == "__main__":
    main()
