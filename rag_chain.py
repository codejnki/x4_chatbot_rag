# rag_chain.py (Final Version with Re-ranking and State Fix)

import json
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from typing import AsyncGenerator, List, Dict, Optional
from thefuzz import process, fuzz

class X4RAGChain:
    """
    Implements a two-stage "Researcher/Actor" RAG pipeline with a re-ranking step.
    """
    def _load_text_file(self, file_path: str, description: str) -> str:
        path = Path(file_path)
        if not path.exists(): raise FileNotFoundError(f"{description} file not found at '{file_path}'")
        return path.read_text("utf-8")

    def _load_json_file(self, file_path: str, description: str) -> dict:
        path = Path(file_path)
        if not path.exists(): raise FileNotFoundError(f"{description} file not found at '{file_path}'")
        return json.loads(path.read_text("utf-8"))

    def __init__(self, vector_store_path="faiss_index", model_name="sentence-transformers/all-MiniLM-L6-v2", 
                 prompt_path="system_prompt.txt", entities_path="x4_keywords_refined.json", 
                 researcher_prompt_path="researcher_prompt.txt"):
        
        self.base_system_prompt = self._load_text_file(prompt_path, "System prompt")
        researcher_template_str = self._load_text_file(researcher_prompt_path, "Researcher prompt")
        self.researcher_prompt_template = ChatPromptTemplate.from_template(researcher_template_str)

        keywords_data = self._load_json_file(entities_path, "Refined Keywords")
        self.keywords = keywords_data.get("keywords", [])
        print(f"Loaded {len(self.keywords)} refined keywords.")

        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        base_vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
        base_retriever = base_vectorstore.as_retriever(search_kwargs={"k": 50})
        
        reranker_model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
        compressor = CrossEncoderReranker(model=reranker_model, top_n=7)
        
        self.retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=base_retriever
        )
        
        self.actor_model = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="not-needed", temperature=0.7)
        self.researcher_model = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="not-needed", temperature=0.0)

        # --- THIS IS THE FIX ---
        # We now explicitly include a placeholder for the context, which is required
        # by the create_stuff_documents_chain function.
        actor_prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.base_system_prompt),
            ("system", "Context from the X4 Foundations wiki:\n{context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ])
        self.actor_chain = create_stuff_documents_chain(self.actor_model, actor_prompt_template)

    def _find_all_entities_in_query(self, query: str) -> List[str]:
        all_matches = process.extract(query, self.keywords, scorer=fuzz.token_set_ratio, limit=5)
        good_matches = [match[0] for match in all_matches if match[1] >= 90]
        return list(set(good_matches))

    async def _run_researcher_step(self, question: str, documents: List[Document]) -> Optional[str]:
        if not documents: return None
        
        context_str = "\n\n---\n\n".join([f"Source: {doc.metadata.get('title', 'Unknown')}\n\n{doc.page_content}" for doc in documents])
        
        research_chain = self.researcher_prompt_template | self.researcher_model
        
        print("--- Running Researcher Step ---")
        response = await research_chain.ainvoke({"question": question, "context": context_str})
        synthesized_context = response.content
        
        if "NO_CLEAR_ANSWER" in synthesized_context or not synthesized_context.strip():
            print("--- Researcher found no clear answer. ---")
            return None
            
        print(f"--- Researcher synthesized context: ---\n{synthesized_context}\n--------------------")
        return synthesized_context

    async def _get_context_stream(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        keywords = self._find_all_entities_in_query(question)
        final_context_str: Optional[str] = None

        if keywords:
            print(f"Found keywords: {keywords}. Retrieving, re-ranking, and researching...")
            retrieved_docs = await self.retriever.ainvoke(question)
            final_context_str = await self._run_researcher_step(question, retrieved_docs)

        if not final_context_str:
            print("Fallback: No keywords found or researcher failed. Using simple semantic retrieval.")
            docs = await self.retriever.ainvoke(question)
            final_context_str = "\n\n".join([doc.page_content for doc in docs])

        final_documents = [Document(page_content=final_context_str)]

        # --- THIS IS THE FIX: Pass an empty list for chat_history ---
        # This forces the Actor to be stateless and only focus on the current question and context.
        async for chunk in self.actor_chain.astream({
            "input": question, 
            "chat_history": [], 
            "context": final_documents
        }):
            yield {"answer": chunk}

    async def stream_query(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        return self._get_context_stream(question, chat_history)