from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from typing import AsyncGenerator

class X4RAGChain:
    """
    Encapsulates the entire RAG pipeline for the X4 Foundations Wiki.
    Initializes all components once to be reused across multiple requests.
    """
    def __init__(self, vector_store_path="faiss_index", model_name="sentence-transformers/all-MiniLM-L6-v2"):
        # --- 1. Load the local vector store and create a retriever ---
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        self.vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
        self.retriever = self.vectorstore.as_retriever()

        # --- 2. Define the LLM ---
        # Connects to the local LM Studio server
        self.model = ChatOpenAI(
            base_url="http://localhost:1234/v1",
            api_key="not-needed",
            temperature=0.1,
        )

        # --- 3. Define the RAG prompt template ---
        template = """
        You are 'Data', an expert AI assistant for the game X4 Foundations.
        Your sole purpose is to answer questions accurately based on the provided context from the X4 wiki.
        If the context does not contain the answer, state that the information is not available in the provided documents.
        Do not use any information outside of the given context. Be concise and factual.

        Context:
        {context}

        Question:
        {question}

        Answer:
        """
        self.prompt = ChatPromptTemplate.from_template(template)

        # --- 4. Chain all the components together ---
        self.rag_chain = (
            {"context": self.retriever, "question": RunnablePassthrough()}
            | self.prompt
            | self.model
            | StrOutputParser()
        )

    async def stream_query(self, question: str) -> AsyncGenerator[str, None]:
        """
        Queries the RAG chain and streams the response.
        This is an asynchronous generator.
        """
        async for chunk in self.rag_chain.astream(question):
            yield chunk