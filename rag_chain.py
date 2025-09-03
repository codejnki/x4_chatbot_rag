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
        self.actor_chain = self._create_actor_chain()

    def _load_config(self):
        self.base_system_prompt = load_text_file(config.SYSTEM_PROMPT_PATH, "System prompt")
        self.researcher_template_str = load_text_file(config.RESEARCHER_PROMPT_PATH, "Researcher prompt")
        self.researcher_prompt_template = ChatPromptTemplate.from_template(self.researcher_template_str)
        
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

    async def _get_context_stream(self, question: str, chat_history: List[BaseMessage]) -> AsyncGenerator[Dict, None]:
        keywords = self._find_all_entities_in_query(question)
        final_context_str: Optional[str] = None

        if keywords:
            logger.info(f"Found keywords: {keywords}. Retrieving, re-ranking, and researching...")
            retrieved_docs = await self.retriever.ainvoke(question)
            final_context_str = await self.researcher.run(question, retrieved_docs)

        if not final_context_str:
            logger.info("Fallback: No keywords found or researcher failed. Using simple semantic retrieval with researcher pass.")
            docs = await self.retriever.ainvoke(question)
            final_context_str = await self.researcher.run(question, docs)

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
