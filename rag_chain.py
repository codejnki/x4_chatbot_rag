# rag_chain.py

import json
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from typing import AsyncGenerator, List, Dict, Optional
from thefuzz import process, fuzz

class X4RAGChain:
    """
    A RAG pipeline that uses a refined keyword list and longest-match fuzzy logic
    to perform robust, precise retrieval from conversational queries.
    """
    def _load_text_file(self, file_path: str, description: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"{description} file not found at '{file_path}'")
        try:
            return path.read_text("utf-8")
        except Exception as e:
            print(f"Error loading {description} file: {e}")
            raise

    def _load_json_file(self, file_path: str, description: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"{description} file not found at '{file_path}'")
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception as e:
            print(f"Error loading {description} file: {e}")
            raise

    def __init__(self, vector_store_path="faiss_index", model_name="sentence-transformers/all-MiniLM-L6-v2", prompt_path="system_prompt.txt", entities_path="x4_keywords_refined.json"):
        # --- 1. Load prompts and the refined keyword list ---
        self.base_system_prompt = self._load_text_file(prompt_path, "System prompt")
        
        keywords_data = self._load_json_file(entities_path, "Refined Keywords")
        self.keywords = keywords_data.get("keywords", [])
        print(f"Loaded {len(self.keywords)} refined keywords for fuzzy matching.")
        if self.keywords:
            print(f"Sample keywords: {self.keywords[:5]}")

        # --- 2. Load retriever and model ---
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        self.vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
        self.retriever = self.vectorstore.as_retriever()
        
        self.model = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="not-needed", temperature=0.7)

        # --- 3. Create the document combination chain ---
        answer_prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.base_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ])
        self.document_chain = create_stuff_documents_chain(self.model, answer_prompt_template)

    def _find_entity_in_query(self, query: str) -> Optional[str]:
        """
        Finds all good fuzzy matches in the query, filters them by a score
        threshold, and then returns the longest one to prioritize specificity.
        """
        # --- THIS IS THE CORRECTED LOGIC ---
        # 1. Get the top 5 candidate matches from the full list.
        all_matches = process.extract(
            query, 
            self.keywords, 
            scorer=fuzz.token_set_ratio, 
            limit=5
        )
        
        # 2. Filter these candidates by our score cutoff.
        good_matches = [match for match in all_matches if match[1] >= 90]
        
        if not good_matches:
            return None
            
        # 3. From the remaining good matches, find the one with the longest string length.
        # This ensures "Hull Parts" is chosen over "Hull".
        best_match = max(good_matches, key=lambda match: len(match[0]))
        return best_match[0]
        # ------------------------------------

    async def stream_query(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        """
        Queries the RAG chain using the robust hybrid fuzzy/semantic search.
        """
        retrieval_query = self._find_entity_in_query(question)
        
        if retrieval_query:
            print(f"Found entity via fuzzy match: '{retrieval_query}'. Using it for precise retrieval.")
        else:
            print("No specific entity found. Using full query for semantic retrieval.")
            retrieval_query = question

        retrieved_docs = await self.retriever.ainvoke(retrieval_query)
        
        async for chunk in self.document_chain.astream(
            {"input": question, "chat_history": chat_history, "context": retrieved_docs}
        ):
            yield {"answer": chunk}
