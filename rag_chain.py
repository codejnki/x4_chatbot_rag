# rag_chain.py (Final Version with Improved Fallback)

import json
import logging
import tiktoken
from pathlib import Path
from openai import APIError
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

logger = logging.getLogger(__name__)

# --- Configuration for Context Management ---
MAX_CONTEXT_TOKENS = 6000
tokenizer = tiktoken.get_encoding("cl100k_base")


class X4RAGChain:
    """
    Implements a two-stage "Researcher/Actor" RAG pipeline with a re-ranking step
    and robust context window management.
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
                 prompt_path="prompts/system_prompt.txt", entities_path="x4_keywords_refined.json",
                 researcher_prompt_path="prompts/researcher_prompt.txt"):

        self.base_system_prompt = self._load_text_file(prompt_path, "System prompt")
        researcher_template_str = self._load_text_file(researcher_prompt_path, "Researcher prompt")
        self.researcher_prompt_template = ChatPromptTemplate.from_template(researcher_template_str)

        keywords_data = self._load_json_file(entities_path, "Refined Keywords")
        self.keywords = keywords_data.get("keywords", [])
        logger.info(f"Loaded {len(self.keywords)} refined keywords.")

        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        base_vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
        base_retriever = base_vectorstore.as_retriever(search_kwargs={"k": 10})

        reranker_model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
        compressor = CrossEncoderReranker(model=reranker_model, top_n=7)

        self.retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=base_retriever
        )

        self.actor_model = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="not-needed", temperature=0.7)
        self.researcher_model = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="not-needed", temperature=0.0)

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
        if not documents:
            return None

        research_chain = self.researcher_prompt_template | self.researcher_model
        
        batches = []
        current_batch = []
        current_tokens = 0

        for doc in documents:
            doc_content = f"Source: {doc.metadata.get('title', 'Unknown')}\n\n{doc.page_content}"
            doc_tokens = len(tokenizer.encode(doc_content))

            if current_tokens + doc_tokens > MAX_CONTEXT_TOKENS:
                if current_batch:
                    batches.append("\n\n---\n\n".join(current_batch))
                current_batch = [doc_content]
                current_tokens = doc_tokens
            else:
                current_batch.append(doc_content)
                current_tokens += doc_tokens
        
        if current_batch:
            batches.append("\n\n---\n\n".join(current_batch))

        logger.info(f"Created {len(batches)} batch(es) for the researcher step.")

        summaries = []
        for i, batch in enumerate(batches):
            logger.info(f"--- Running Researcher on Batch {i+1}/{len(batches)} ---")
            try:
                response = await research_chain.ainvoke({"question": question, "context": batch})
                summary = response.content
                if "NO_CLEAR_ANSWER" not in summary and summary.strip():
                    summaries.append(summary)
            except APIError as e:
                logger.error(f"API Error during researcher batch {i+1}: {e}")
                continue

        if not summaries:
            logger.info("--- Researcher found no clear answer in any batch. ---")
            return None

        if len(summaries) > 1:
            logger.info("--- Consolidating multiple researcher summaries ---")
            combined_summaries = "\n\n---\n\n".join(summaries)
            final_response = await research_chain.ainvoke({"question": question, "context": combined_summaries})
            synthesized_context = final_response.content
        else:
            synthesized_context = summaries[0]
            
        logger.info(f"--- Final Researcher synthesized context: ---\n{synthesized_context}\n--------------------")
        return synthesized_context

    async def _get_context_stream(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        keywords = self._find_all_entities_in_query(question)
        final_context_str: Optional[str] = None

        if keywords:
            logger.info(f"Found keywords: {keywords}. Retrieving, re-ranking, and researching...")
            retrieved_docs = await self.retriever.ainvoke(question)
            final_context_str = await self._run_researcher_step(question, retrieved_docs)

        # --- IMPROVED FALLBACK LOGIC ---
        if not final_context_str:
            logger.info("Fallback: No keywords found or researcher failed. Using simple semantic retrieval with researcher pass.")
            # Retrieve the top 5 documents semantically
            docs = await self.retriever.ainvoke(question, top_k=5) 
            # Run these documents through the same robust researcher step
            final_context_str = await self._run_researcher_step(question, docs)

        # If all attempts fail, provide a clear "I don't know" message.
        if not final_context_str:
            final_context_str = "NO_CLEAR_ANSWER"
        
        final_documents = [Document(page_content=final_context_str)]

        async for chunk in self.actor_chain.astream({
            "input": question,
            "chat_history": [],
            "context": final_documents
        }):
            yield {"answer": chunk}

    async def stream_query(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        return self._get_context_stream(question, chat_history)