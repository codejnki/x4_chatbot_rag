# 01b_summarize_md.py

import argparse
import logging
import tiktoken
import config
from openai import OpenAI, APIError
from pathlib import Path
from tqdm import tqdm
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
DATA_SOURCE_DIR = Path("x4-foundations-wiki")
MD_PAGES_DIR = Path(DATA_SOURCE_DIR, "pages_md")
SUMMARIZED_PAGES_DIR = Path(DATA_SOURCE_DIR, "pages_summarized")

# --- LLM Configuration ---
API_KEY = "not-needed"
SUMMARIZER_PROMPT_PATH = "prompts/document_summarizer_prompt.txt"
MAX_CONTEXT_TOKENS = 6000
LIST_SUMMARY_THRESHOLD = 10

# --- Globals ---
CLIENT = OpenAI(base_url=config.BASE_URL, api_key=API_KEY)
SUMMARIZER_PROMPT_TEMPLATE = Path(SUMMARIZER_PROMPT_PATH).read_text("utf-8")
TOKENIZER = tiktoken.get_encoding("cl100k_base")
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
            model=config.SUMMARY_MODEL_NAME,
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

def main():
    parser = argparse.ArgumentParser(description="Summarize and enrich a single Markdown file.")
    parser.add_argument("input_file", type=str, help="Path to the input Markdown file relative to the MD pages directory.")

    args = parser.parse_args()
    clean_input_file = args.input_file.strip()


    input_file_path = Path(MD_PAGES_DIR, clean_input_file)
    output_file_path = Path(SUMMARIZED_PAGES_DIR, clean_input_file)

    if not input_file_path.exists():
        logger.error(f"Input file not found: {input_file_path}")
        return

    with open(input_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    enriched_content = summarize_and_enrich_content(md_content, input_file_path)

    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(enriched_content)

    logger.info(f"Successfully summarized and enriched {input_file_path} to {output_file_path}")

if __name__ == "__main__":
    main()
