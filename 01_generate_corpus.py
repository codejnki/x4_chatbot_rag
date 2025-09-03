# 01_generate_corpus.py

import os
import json
import re
import tiktoken
import logging
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm
from openai import OpenAI, APIError
from pathlib import Path
from markdown_it import MarkdownIt
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List

# --- Logging Configuration ---
class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("console.log"),
        TqdmLoggingHandler()
    ]
)

logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

# --- Configuration ---
DATA_SOURCE_DIR = Path(r"x4-foundations-wiki")
SANITIZED_DIR = DATA_SOURCE_DIR / "hashed_pages"
PATH_MAP_FILE = DATA_SOURCE_DIR / "path_map.json"
OUTPUT_FILE = "x4_wiki_corpus.json"

# --- LLM Configuration ---
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
API_KEY = "not-needed"
SUMMARIZER_PROMPT_PATH = "prompts/document_summarizer_prompt.txt"
MAX_CONTEXT_TOKENS = 6000
LIST_SUMMARY_THRESHOLD = 10

# --- Globals ---
CLIENT = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=API_KEY)
SUMMARIZER_PROMPT_TEMPLATE = Path(SUMMARIZER_PROMPT_PATH).read_text("utf-8")
TOKENIZER = tiktoken.get_encoding("cl100k_base")
MD_PARSER = MarkdownIt()
PROMPT_TEMPLATE_SIZE = len(TOKENIZER.encode(SUMMARIZER_PROMPT_TEMPLATE.format(task="", content="")))
EFFECTIVE_CONTEXT_SIZE = MAX_CONTEXT_TOKENS - PROMPT_TEMPLATE_SIZE - 200 # Safety buffer

def call_summarizer(content: str, task: str) -> str:
    try:
        if not content or len(content.split()) < 10:
            return ""
        formatted_prompt = SUMMARIZER_PROMPT_TEMPLATE.format(task=task, content=content)
        prompt_tokens = len(TOKENIZER.encode(formatted_prompt))
        if prompt_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(f"Prompt for task {task} is too large ({prompt_tokens} tokens).")
            return ""
        response = CLIENT.chat.completions.create(
            model="local-model",
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except APIError as e:
        logger.error(f"API error during summarization task {task}: {e}")
        return ""
    except Exception as e:
        logger.error(f"An unexpected error occurred during summarization task {task}: {e}")
        return ""

def recursive_summarize(texts: List[str], task: str) -> str:
    """Recursively summarizes a list of texts until it fits in the context window."""
    if not texts:
        return ""
    
    combined_text = "\n\n---\n\n".join(texts)
    
    if len(TOKENIZER.encode(combined_text)) <= EFFECTIVE_CONTEXT_SIZE:
        return call_summarizer(combined_text, task)
    else:
        logger.info(f"Content for recursive summarization is too large. Splitting {len(texts)} texts in half.")
        mid_point = len(texts) // 2
        first_half_summary = recursive_summarize(texts[:mid_point], task)
        second_half_summary = recursive_summarize(texts[mid_point:], task)
        
        return recursive_summarize([first_half_summary, second_half_summary], "SUMMARIZE_SUMMARIES")

def get_sections(md_content: str):
    lines = md_content.split('\n')
    sections = []
    current_section_content = []
    current_section_title = ""
    for line in lines:
        if line.startswith('#'):
            if current_section_content:
                sections.append({"title": current_section_title, "content": '\n'.join(current_section_content)})
            current_section_title = line
            current_section_content = [line]
        else:
            current_section_content.append(line)
    if current_section_content:
        sections.append({"title": current_section_title, "content": '\n'.join(current_section_content)})
    return sections

def summarize_and_enrich_content(md_content: str, file_path_for_logging: Path) -> str:
    sections = get_sections(md_content)
    if not sections:
        return md_content

    enriched_sections = []
    section_summaries = []

    for section in tqdm(sections, desc=f"Summarizing Sections in {file_path_for_logging.name}", leave=False):
        section_content = section['content']
        section_title = section['title']
        summary = ""
        section_tokens = len(TOKENIZER.encode(section_content))

        if section_tokens > EFFECTIVE_CONTEXT_SIZE:
            logger.info(f"Section '{section_title[:50]}...' is too large ({section_tokens} tokens). Splitting into batches.")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=EFFECTIVE_CONTEXT_SIZE,
                chunk_overlap=200,
                length_function=lambda text: len(TOKENIZER.encode(text)),
            )
            chunks = text_splitter.split_text(section_content)
            chunk_summaries = []
            for chunk in tqdm(chunks, desc=f"Batch-summarizing '{section_title[:20]}...'", leave=False):
                task = "SUMMARIZE_LIST" if chunk.count('* ') + chunk.count('- ') > LIST_SUMMARY_THRESHOLD else "SUMMARIZE_SECTION"
                chunk_summary = call_summarizer(chunk, task)
                if chunk_summary:
                    chunk_summaries.append(chunk_summary)
            
            summary = recursive_summarize(chunk_summaries, "SUMMARIZE_SUMMARIES")
        else:
            task = "SUMMARIZE_LIST" if section_content.count('* ') + section_content.count('- ') > LIST_SUMMARY_THRESHOLD else "SUMMARIZE_SECTION"
            summary = call_summarizer(section_content, task)
        
        if summary:
            enriched_sections.append(f"{summary}\n\n{section_content}")
            section_summaries.append(summary)
        else:
            enriched_sections.append(section_content)

    if len(section_summaries) > 1:
        final_summary = recursive_summarize(section_summaries, "SUMMARIZE_SUMMARIES")
        if final_summary:
            return f"# Document Summary\n\n{final_summary}\n\n---\n\n" + "\n\n---\n\n".join(enriched_sections)
    
    return "\n\n---\n\n".join(enriched_sections)

def process_html_file(file_path, path_map):
    try:
        relative_path = Path(file_path).relative_to(SANITIZED_DIR)
        path_key = str(relative_path).replace(os.path.sep, '/')
        original_path = path_map.get(path_key)
        if not original_path:
            logger.warning(f"Could not find original path for {file_path}. Skipping.")
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'lxml')
        main_content = soup.find('main', id="mainContentArea")
        if not main_content: return None
        title_tag = main_content.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"
        body_container = main_content.find('div', id="xwikicontent")
        if not body_container: return None
        for a_tag in body_container.find_all('a'):
            a_tag.unwrap()
        body_markdown = md(str(body_container), heading_style="ATX", strip=['img'])
        full_markdown = f"# {title}\n\n{body_markdown}"
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown).strip()
        enriched_content = summarize_and_enrich_content(cleaned_markdown, file_path)
        return {'source': os.path.dirname(original_path), 'title': title, 'content': enriched_content}
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        return None

def main():
    logger.info("Starting Phase 1: Data Preparation (with sequential summarization)")
    try:
        with open(PATH_MAP_FILE, 'r', encoding='utf-8') as f:
            path_map = json.load(f)
    except FileNotFoundError:
        logger.error(f"Path map not found at '{PATH_MAP_FILE}'. Run 'make data' first.")
        return

    target_files = list(SANITIZED_DIR.glob('**/*.html'))
    logger.info(f"Found {len(target_files)} pages to process.")

    processed_docs = []
    for file_path in tqdm(target_files, desc="Processing & Summarizing Files"):
        result = process_html_file(file_path, path_map)
        if result:
            processed_docs.append(result)

    logger.info(f"Successfully processed and enriched {len(processed_docs)} documents.")
    logger.info(f"Saving the processed data to '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_docs, f, indent=2, ensure_ascii=False)
    logger.info(f"Corpus saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()