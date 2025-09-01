# rag_chain.py

from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from typing import AsyncGenerator, List, Dict

class X4RAGChain:
    """
    Encapsulates a conversational RAG pipeline for the X4 Foundations Wiki.
    It uses chat history to rephrase questions for better context retrieval.
    """
    def __init__(self, vector_store_path="faiss_index", model_name="sentence-transformers/all-MiniLM-L6-v2"):
        # --- 1. Load retriever and model (unchanged) ---
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        self.vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
        self.retriever = self.vectorstore.as_retriever()
        
        self.model = ChatOpenAI(
            base_url="http://localhost:1234/v1",
            api_key="not-needed",
            temperature=0.1,
        )

        # --- 2. Create a History-Aware Prompt for rephrasing the question ---
        # This prompt instructs the LLM to take the latest user question and the chat history,
        # and create a new, standalone question.
        rephrase_prompt = ChatPromptTemplate.from_messages([
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            ("user", "Given the above conversation, generate a search query to look up in order to get information relevant to the conversation")
        ])

        # This chain combines the prompt, model, and retriever. It will first rephrase the
        # user's input, then use that to query the vector store.
        history_aware_retriever = create_history_aware_retriever(
            self.model, self.retriever, rephrase_prompt
        )

        # --- 3. Create a Prompt for Generating the Final Answer ---
        # This prompt includes the chat history and the retrieved context.
        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are 'Data', an expert AI assistant for the game X4 Foundations. Your sole purpose is to answer questions accurately based on the provided context from the X4 wiki. If the context does not contain the answer, state that the information is not available in the provided documents. Do not use any information outside of the given context. Be concise and factual.\n\nContext:\n{context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ])

        # This chain combines the prompt and the model to generate the final answer.
        document_chain = create_stuff_documents_chain(self.model, answer_prompt)

        # --- 4. Combine the two chains into a final retrieval chain ---
        # This is the final chain we will invoke. It orchestrates the entire process.
        self.rag_chain = create_retrieval_chain(history_aware_retriever, document_chain)

    async def stream_query(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        """
        Queries the conversational RAG chain and streams the response dictionary.
        """
        async for chunk in self.rag_chain.astream({"input": question, "chat_history": chat_history}):
            yield chunk


