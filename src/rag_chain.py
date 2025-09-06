# src/rag_chain.py
import logging
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from typing import AsyncGenerator, List, Dict, Optional
from thefuzz import process, fuzz

import config
from researcher import Researcher
from retriever import create_retriever
from file_utils import load_text_file, load_json_file

logger = logging.getLogger(__name__)

class X4RAGChain:
    def __init__(self):
        self._load_config()
        self.retriever = create_retriever()
        self.researcher = Researcher(self.researcher_prompt_template, self.researcher_template_str)
        self.actor_model = ChatOpenAI(base_url=config.BASE_URL, api_key=config.API_KEY, temperature=0.7)
        # New model instance for the query rewriter to ensure it's a distinct logical step
        self.query_rewriter_model = ChatOpenAI(base_url=config.BASE_URL, api_key=config.API_KEY, temperature=0.0)
        self.actor_chain = self._create_actor_chain()
        self.rewriter_chain = self.query_rewriter_prompt_template | self.query_rewriter_model


    def _load_config(self):
        self.base_system_prompt = load_text_file(config.SYSTEM_PROMPT_PATH, "System prompt")
        self.researcher_template_str = load_text_file(config.RESEARCHER_PROMPT_PATH, "Researcher prompt")
        self.query_rewriter_template_str = load_text_file("prompts/query_rewriter_prompt.txt", "Query rewriter prompt")
        
        self.researcher_prompt_template = ChatPromptTemplate.from_template(self.researcher_template_str)
        self.query_rewriter_prompt_template = ChatPromptTemplate.from_template(self.query_rewriter_template_str)
        
        keywords_data = load_json_file(config.KEYWORDS_PATH, "Refined Keywords")
        self.keywords = keywords_data.get("keywords", [])
        logger.info(f"Loaded {len(self.keywords)} refined keywords.")

    def _create_actor_chain(self):
        actor_prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.base_system_prompt),
            ("system", "Context from the X4 Foundations wiki:\n{context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ])
        return create_stuff_documents_chain(self.actor_model, actor_prompt_template)

    def _find_all_entities_in_query(self, query: str) -> List[str]:
        all_matches = process.extract(query, self.keywords, scorer=fuzz.token_set_ratio, limit=5)
        good_matches = [match[0] for match in all_matches if match[1] >= 90]
        return list(set(good_matches))
    
    async def _rewrite_query(self, question: str, context_docs: List[Document]) -> str:
        """Analyzes failed context and rewrites the question to be more specific."""
        logger.info("--- Attempting to rewrite query for clarity... ---")
        context_str = "\n\n---\n\n".join([doc.page_content for doc in context_docs])
        
        response = await self.rewriter_chain.ainvoke({
            "question": question,
            "context": context_str
        })
        
        rewritten_question = response.content.strip()
        logger.info(f"--- Rewritten query: '{rewritten_question}' ---")
        return rewritten_question


    async def _get_context_stream(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        # --- Pass 1: Initial Retrieval and Research ---
        logger.info("--- Performing initial retrieval and research pass... ---")
        retrieved_docs = await self.retriever.ainvoke(question)
        final_context_str = await self.researcher.run(question, retrieved_docs)

        # --- Pass 2: Self-Correction via Query Rewriting (if needed) ---
        if not final_context_str:
            logger.info("--- Initial research failed. Triggering self-correction pass. ---")
            rewritten_question = await self._rewrite_query(question, retrieved_docs)
            
            # If the rewritten question is the same as the original, we're in a loop.
            if rewritten_question.lower() == question.lower():
                 logger.warning("Query rewrite resulted in the same question. Aborting self-correction.")
                 final_context_str = "NO_CLEAR_ANSWER"
            else:
                # Perform a second retrieval and research pass with the new query
                second_pass_docs = await self.retriever.ainvoke(rewritten_question)
                final_context_str = await self.researcher.run(rewritten_question, second_pass_docs)

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
        async for chunk in self._get_context_stream(question, chat_history):
            yield chunk
