# rag_chain.py (Modified Version)

import json
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from typing import AsyncGenerator, List, Dict, Optional

class X4RAGChain:
    """
    A RAG pipeline that uses a pre-compiled list of entities to perform
    a precise keyword search before falling back to a general semantic search.
    """

    def _load_json_file(self, file_path: str, description: str):
        """Helper to load and validate JSON files."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"{description} file not found at '{file_path}'")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {description} file: {e}")
            raise

    def __init__(self, vector_store_path="faiss_index", model_name="sentence-transformers/all-MiniLM-L6-v2", prompt_path="system_prompt.txt", entities_path="x4_entities.json"):
        # --- 1. Load prompts and entity list ---
        system_prompt_content = self._load_json_file(prompt_path, "System prompt")
        self.base_system_prompt = system_prompt_content if isinstance(system_prompt_content, str) else system_prompt_content.get("prompt", "")
        if "{context}" not in self.base_system_prompt:
             raise ValueError("The system prompt must include a '{context}' placeholder.")
        
        entities_data = self._load_json_file(entities_path, "Entities")
        # Store entities for quick lookup. We store the lowercase version for case-insensitive matching.
        self.entities = sorted(entities_data.get("entities", []), key=len, reverse=True)


        # --- 2. Load retriever and model ---
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        self.vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
        self.retriever = self.vectorstore.as_retriever()
        
        self.model = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="not-needed", temperature=0.7)

        # --- 3. Create the final answer prompt ---
        answer_prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.base_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ])

        # --- 4. Create the final retrieval chain ---
        document_chain = create_stuff_documents_chain(self.model, answer_prompt_template)
        self.rag_chain = create_retrieval_chain(self.retriever, document_chain)

    def _find_entity_in_query(self, query: str) -> Optional[str]:
        """
        Scans the user's query for the first and longest matching entity from the pre-compiled list.
        Returns the entity name if found, otherwise None.
        """
        query_lower = query.lower()
        for entity in self.entities:
            if entity.lower() in query_lower:
                return entity # Return the original cased entity name
        return None

    async def stream_query(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        """
        Queries the RAG chain. It first attempts to find a known entity in the question
        for a precise search, falling back to a general search if no entity is found.
        """
        # Determine the best query to use for retrieval
        entity_found = self._find_entity_in_query(question)
        
        # The 'input' to the rag_chain is used for both retrieval and the final prompt.
        # By using the clean entity name for retrieval, we get better results.
        # The full 'question' is still available in the final prompt via chat history.
        retrieval_query = entity_found if entity_found else question
        
        if entity_found:
            print(f"Found entity: '{entity_found}'. Using it for precise retrieval.")
        else:
            print("No specific entity found. Using full query for semantic retrieval.")

        # LangChain's `create_retrieval_chain` cleverly uses the 'input' for retrieval,
        # but the prompt template populates '{input}' with the original, full question.
        # To make our keyword search effective, we need to control the retrieval query explicitly.
        
        # Step 1: Explicitly retrieve documents with our chosen query
        retrieved_docs = await self.retriever.ainvoke(retrieval_query)
        
        # Step 2: Invoke the rest of the chain with the retrieved docs and original inputs
        async for chunk in self.rag_chain.astream(
            {"input": question, "chat_history": chat_history, "context": retrieved_docs}
        ):
            yield chunk

