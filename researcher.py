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
            logger.info(f"Content for recursive summarization is too large. Splitting {len(texts)} texts in half.")
            mid_point = len(texts) // 2
            first_half_summary = await self._recursive_summarize(question, texts[:mid_point])
            second_half_summary = await self._recursive_summarize(question, texts[mid_point:])

            return await self._recursive_summarize(question, [first_half_summary, second_half_summary])

    async def run(self, question: str, documents: List[Document]) -> Optional[str]:
        if not documents:
            return None

        summaries = []
        for i, doc in enumerate(documents):
            doc_content = f"Source: {doc.metadata.get('title', 'Unknown')}\n\n{doc.page_content}"
            logger.info(f"--- Running Researcher on Document {i + 1}/{len(documents)} ---")

            summary = await self._recursive_summarize(question, [doc_content])
            if "NO_CLEAR_ANSWER" not in summary and summary.strip():
                summaries.append(summary)

        if not summaries:
            logger.info("--- Researcher found no clear answer in any document. ---")
            return None

        if len(summaries) > 1:
            logger.info("--- Consolidating multiple researcher summaries ---")
            final_synthesized_context = await self._recursive_summarize(question, summaries)
        else:
            final_synthesized_context = summaries[0]

        logger.info(f"--- Final Researcher synthesized context: ---\n{final_synthesized_context}\n--------------------")
        return final_synthesized_context