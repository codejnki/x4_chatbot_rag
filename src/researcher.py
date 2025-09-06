import logging
import tiktoken
from openai import APIError
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from typing import List, Optional
import config

logger = logging.getLogger(__name__)
TOKENIZER = tiktoken.get_encoding("cl100k_base")

class Researcher:
    def __init__(self, researcher_prompt_template, researcher_template_str):
        self.researcher_model = ChatOpenAI(base_url=config.BASE_URL, api_key=config.API_KEY, temperature=0.0)
        self.researcher_chain = researcher_prompt_template | self.researcher_model
        prompt_template_size = len(TOKENIZER.encode(researcher_template_str.format(question="", context="")))
        self.effective_context_size = config.MAX_CONTEXT_TOKENS - prompt_template_size - 200  # Safety buffer

    async def _recursive_summarize(self, question: str, texts: List[str]) -> str:
        if not texts:
            return ""

        combined_text = "\n\n---\n\n".join(texts)

        if len(TOKENIZER.encode(combined_text)) <= self.effective_context_size:
            try:
                response = await self.researcher_chain.ainvoke({"question": question, "context": combined_text})
                return response.content.strip()
            except APIError as e:
                logger.error(f"API Error during summarization: {e}")
                return "NO_CLEAR_ANSWER"
        else:
            logger.info(f"Content for recursive summarization is too large. Splitting text in half.")
            # Simple split for now, can be improved with more sophisticated chunking if needed
            mid_point = len(combined_text) // 2
            first_half = combined_text[:mid_point]
            second_half = combined_text[mid_point:]
            
            # Recursively summarize each half
            first_half_summary = await self._recursive_summarize(question, [first_half])
            second_half_summary = await self._recursive_summarize(question, [second_half])
            
            # Combine the summaries of the two halves
            return await self._recursive_summarize(question, [first_half_summary, second_half_summary])

    async def run(self, question: str, documents: List[Document]) -> Optional[str]:
        if not documents:
            return None

        # --- MODIFICATION START ---
        # Consolidate all document content BEFORE calling the LLM.
        # This allows the LLM to see all context at once and resolve ambiguities.
        
        logger.info(f"--- Consolidating {len(documents)} retrieved documents for researcher... ---")
        
        all_doc_content = []
        for doc in documents:
            doc_content = f"Source: {doc.metadata.get('title', 'Unknown')}\n\n{doc.page_content}"
            all_doc_content.append(doc_content)

        # Perform a single, powerful synthesis call on the combined text
        final_synthesized_context = await self._recursive_summarize(question, all_doc_content)
        # --- MODIFICATION END ---

        if not final_synthesized_context or "NO_CLEAR_ANSWER" in final_synthesized_context:
            logger.info("--- Researcher found no clear answer in the consolidated documents. ---")
            return None

        logger.info(f"--- Final Researcher synthesized context: ---\n{final_synthesized_context}\n--------------------")
        return final_synthesized_context
