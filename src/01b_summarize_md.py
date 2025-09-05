# 01b_summarize_md.py

import argparse
import logging
import tiktoken
import config
from openai import OpenAI, APIError
from pathlib import Path
from tqdm import tqdm
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Optional
from dataclasses import dataclass, field
from markdown_it import MarkdownIt
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

# --- Configuration ---
DATA_SOURCE_DIR = Path("x4-foundations-wiki")
MD_PAGES_DIR = Path(DATA_SOURCE_DIR, "pages_md")
SUMMARIZED_PAGES_DIR = Path(DATA_SOURCE_DIR, "pages_summarized")

# --- New Dataclass for Tree Structure ---
@dataclass
class Section:
    title: str
    level: int
    content: str = ""
    summary: str = ""
    children: List['Section'] = field(default_factory=list)
    parent: Optional['Section'] = None

    def __repr__(self):
        return f"Section(title='{self.title}', level={self.level}, children={len(self.children)})"

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
        if not content:
            return ""
        if len(content.split()) < 10:
            return content.strip() # Returns the original content if it is too short.
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

def build_section_tree(md_content: str) -> Section:
    """Parses markdown content into a hierarchical tree of Section objects."""
    md = MarkdownIt()
    tokens = md.parse(md_content)

    root = Section(title="root", level=0)
    node_stack = [root]
    current_content_parts = []

    for i, token in enumerate(tokens):
        if token.type == 'heading_open':
            # 1. Assign accumulated content to the previous section
            # The content belongs to the node currently at the top of the stack.
            node_stack[-1].content = "".join(current_content_parts).strip()
            current_content_parts = [] # Reset for the new section

            # 2. Create and place the new section node
            level = int(token.tag[1:])
            # The title is in the next token (type: 'inline')
            title = tokens[i+1].content.strip() if (i+1) < len(tokens) else ""
            
            new_node = Section(title=title, level=level)

            while node_stack[-1].level >= level:
                node_stack.pop()
            
            parent = node_stack[-1]
            parent.children.append(new_node)
            new_node.parent = parent
            node_stack.append(new_node)
        
        # 3. Accumulate content for the current section
        # We collect content from any token that isn't a heading.
        elif token.type not in ['heading_open', 'heading_close']:
            if token.content:
                current_content_parts.append(token.content)

    # After the loop, assign any remaining content to the last section processed
    if current_content_parts:
        node_stack[-1].content = "".join(current_content_parts).strip()
        
    # The root node's content is everything before the first heading
    if root.children:
        root.content = root.content.split(root.children[0].title, 1)[0].strip()

    return root

def summarize_tree_post_order(node: Section):
    """Recursively summarizes the tree from the bottom up (post-order traversal)."""
    for child in node.children:
        summarize_tree_post_order(child)

    # For parent nodes, combine their content with the summaries of their children
    child_summaries = "\n".join([f"Sub-section '{c.title}': {c.summary}" for c in node.children if c.summary])

    # Content to be summarized for the current node
    content_to_summarize = node.content
    if child_summaries:
        content_to_summarize += "\n\n" + "Summaries of sub-sections:\n" + child_summaries

    # Avoid summarizing the root container if it has no direct content and no child summaries
    if node.level == 0 and not node.content.strip() and not child_summaries:
        node.summary = ""
        return

    summary_text = ""
    section_tokens = len(TOKENIZER.encode(content_to_summarize))

    if section_tokens > EFFECTIVE_CONTEXT_SIZE:
        logger.info(f"Section '{node.title[:50]}...' is too large ({section_tokens} tokens). Splitting for summarization.")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=EFFECTIVE_CONTEXT_SIZE,
            chunk_overlap=200,
            length_function=lambda text: len(TOKENIZER.encode(text)),
        )
        texts = text_splitter.split_text(content_to_summarize)
        summary_text = recursive_summarize(texts, "SUMMARIZE_SECTION")
    else:
        summary_text = call_summarizer(content_to_summarize, "SUMMARIZE_SECTION")

    node.summary = summary_text

def format_summary_appendix(node: Section) -> str:
    """Formats the collected summaries into a markdown appendix, respecting hierarchy."""
    if not node.summary and not any(child.summary for child in node.children):
        return ""

    parts = []
    # Only add a header for non-root nodes that have a summary
    if node.level > 0 and node.summary:
        header = '#' * (node.level + 1) # Offset for "Executive Summary" H1
        parts.append(f"\n\n{header} {node.title}\n{node.summary}")
    # Special case for root node with content
    elif node.level == 0 and node.summary:
        parts.append(f"\n\n## Overview\n{node.summary}")


    for child in node.children:
        parts.append(format_summary_appendix(child))

    return "".join(parts)

def summarize_and_enrich_content(md_content: str, file_path_for_logging: Path) -> str:
    logger.info(f"Building section tree for {file_path_for_logging.name}...")
    document_tree = build_section_tree(md_content)

    # If the document has no sections and is short, don't summarize
    if not document_tree.children and len(TOKENIZER.encode(md_content)) < 500:
        logger.info("Document is short and has no sections, skipping summarization.")
        return md_content

    logger.info(f"Summarizing document tree for {file_path_for_logging.name}...")
    summarize_tree_post_order(document_tree)

    logger.info(f"Formatting summary appendix for {file_path_for_logging.name}...")
    summary_appendix_content = format_summary_appendix(document_tree)

    if summary_appendix_content:
        summary_appendix = "\n\n---\n\n# Executive Summary" + summary_appendix_content
        return md_content + summary_appendix

    return md_content

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