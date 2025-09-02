from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# --- Configuration ---
VECTOR_STORE_PATH = "faiss_index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# This should match the model you are serving with LM Studio
LLM_MODEL_NAME = "Meta-Llama-3-8B-Instruct-GGUF" 

# --- Main Logic ---
def main():
    """
    Loads the vector store and the LLM, then runs a RAG query.
    """
    print("--- Starting Phase 3: Retrieval and Generation ---")

    # 1. Load the existing vector store and embedding model
    print("Loading vector store and embedding model...")
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': False}
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
    vector_store = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
    # The allow_dangerous_deserialization flag is needed for loading FAISS indexes created with older LangChain versions.
    # It's safe in our context as we created the file ourselves.
    
    retriever = vector_store.as_retriever()
    print("Vector store loaded successfully.")

    # 2. Initialize the LLM from the local LM Studio server
    print(f"Initializing LLM '{LLM_MODEL_NAME}' from local server...")
    llm = ChatOllama(model=LLM_MODEL_NAME)
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
    # This chain defines the entire RAG process.
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
    
    # The .invoke() method runs the chain with the given input.
    response = chain.invoke(question)
    
    print("\n--- LLM Response ---")
    print(response)
    print("\n--- RAG process complete ---")

if __name__ == "__main__":
    main()