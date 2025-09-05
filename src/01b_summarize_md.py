# 01b_summarize_md.py

import argparse
import logging
import re
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
CHANGELOG_KEYWORDS = ["changelog", "patch history"]

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

API_KEY = "not-needed"
SUMMARIZER_PROMPT_PATH = "prompts/document_summarizer_prompt.txt"
MAX_CONTEXT_TOKENS = 6000
LIST_SUMMARY_THRESHOLD = 10

CLIENT = OpenAI(base_url=config.BASE_URL, api_key=API_KEY)
SUMMARIZER_PROMPT_TEMPLATE = Path(SUMMARIZER_PROMPT_PATH).read_text("utf-8")
TOKENIZER = tiktoken.get_encoding("cl100k_base")
PROMPT_TEMPLATE_SIZE = len(TOKENIZER.encode(SUMMARIZER_PROMPT_TEMPLATE.format(task="", content="", context_path="")))
EFFECTIVE_CONTEXT_SIZE = MAX_CONTEXT_TOKENS - PROMPT_TEMPLATE_SIZE - 200

def is_changelog_file(file_path: Path, md_content: str) -> bool:
    """Checks if a file is a changelog based on its name or content."""
    for keyword in CHANGELOG_KEYWORDS:
        if keyword in file_path.name.lower():
            return True
    if any(keyword in md_content[:200].lower() for keyword in CHANGELOG_KEYWORDS):
        return True
    return False

def strip_until_newline(text: str) -> str:
    return re.sub(r'^.*\n', '', text, count=1)

def call_summarizer(content: str, task: str, context_path: str) -> str:
    try:
        if not content.strip():
            return ""
        if len(content.split()) < 10:
             return strip_until_newline(content.strip())

        formatted_prompt = SUMMARIZER_PROMPT_TEMPLATE.format(task=task, content=content, context_path=context_path)
        prompt_tokens = len(TOKENIZER.encode(formatted_prompt))

        if prompt_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(f"Prompt for task {task} with context '{context_path}' is too large ({prompt_tokens} tokens).")
            return ""
        response = CLIENT.chat.completions.create(
            model=config.SUMMARY_MODEL_NAME,
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip() # type: ignore
    except APIError as e:
        logger.error(f"API error during summarization task {task} with context '{context_path}': {e}")
        return ""
    except Exception as e:
        logger.error(f"An unexpected error occurred during summarization task {task} with context '{context_path}': {e}")
        return ""

def recursive_summarize(texts: List[str], task: str, context_path: str) -> str:
    if not texts:
        return ""
    
    combined_text = "\n\n---\n\n".join(texts)
    
    if len(TOKENIZER.encode(combined_text)) <= EFFECTIVE_CONTEXT_SIZE:
        return call_summarizer(combined_text, task, context_path)
    else:
        logger.info(f"Content for recursive summarization is too large. Splitting {len(texts)} texts in half.")
        mid_point = len(texts) // 2
        first_half_summary = recursive_summarize(texts[:mid_point], task, context_path)
        second_half_summary = recursive_summarize(texts[mid_point:], task, context_path)
        
        return recursive_summarize([first_half_summary, second_half_summary], "SUMMARIZE_SUMMARIES", context_path)

def build_section_tree(md_content: str) -> Section:
    """
    Builds a hierarchical tree of sections from markdown content, preserving the
    original markdown within each section.
    """
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_content)
    lines = md_content.splitlines()

    root = Section(title="root", level=0)
    node_stack = [root]
    
    last_line = 0

    for i, token in enumerate(tokens):
        if token.type == 'heading_open':
            current_heading_start_line = token.map[0]
            
            content_lines = lines[last_line:current_heading_start_line]
            node_stack[-1].content = "\n".join(content_lines).strip()

            last_line = token.map[1]

            level = int(token.tag[1:])
            title = tokens[i+1].content.strip() if (i+1) < len(tokens) else ""
            new_node = Section(title=title, level=level)

            while node_stack[-1].level >= level:
                node_stack.pop()
            
            parent = node_stack[-1]
            parent.children.append(new_node)
            new_node.parent = parent
            node_stack.append(new_node)

    if last_line < len(lines):
        content_lines = lines[last_line:]
        node_stack[-1].content = "\n".join(content_lines).strip()
    
    return root

def summarize_tree_post_order(node: Section, context_path: str = ""):
    """Recursively summarizes the tree from the bottom up (post-order traversal)."""
    if node.level == 0:
        first_h1 = next((child for child in node.children if child.level == 1), None)
        context_path = first_h1.title if first_h1 else "Document Overview"
    
    for child in node.children:
        child_context_path = f"{context_path} > {child.title}"
        summarize_tree_post_order(child, child_context_path)

    child_summaries = "".join([f"Sub-section '{c.title}': {c.summary}" for c in node.children if c.summary])

    content_to_summarize = node.content
    if child_summaries:
        content_to_summarize += "\n\n" + "Summaries of sub-sections:\n" + child_summaries

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
        summary_text = recursive_summarize(texts, "SUMMARIZE_SECTION", context_path=context_path)
    else:
        summary_text = call_summarizer(content_to_summarize, "SUMMARIZE_SECTION", context_path=context_path)

    node.summary = summary_text
    
    section_tables = find_all_tables_in_md(node.content)
    if section_tables:
        all_unrolled_content = ["\n\n---\n\n## Unrolled Table Data"]
        for i, table_md in enumerate(section_tables):
            unrolled_table = unroll_single_table(table_md)
            if unrolled_table:
                all_unrolled_content.append(f"\n\n**Table {i+1}**")
                all_unrolled_content.append(unrolled_table)
        
        if len(all_unrolled_content) > 1:
             node.summary += "".join(all_unrolled_content)

def format_summary_appendix(node: Section) -> str:
    """Formats the collected summaries into a markdown appendix, respecting hierarchy."""
    if not node.summary and not any(child.summary for child in node.children):
        return ""

    parts = []
    if node.level > 0 and node.summary:
        header = '#' * (node.level + 1)
        parts.append(f"\n\n{header} {node.title}\n{node.summary}")
    elif node.level == 0 and node.summary:
        parts.append(f"\n\n## Overview\n{node.summary}")

    for child in node.children:
        parts.append(format_summary_appendix(child))

    return "".join(parts)

def find_all_tables_in_md(md_content: str) -> List[str]:
    """Finds all complete Markdown tables in a string."""
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_content)
    lines = md_content.splitlines()
    tables = []

    for token in tokens:
        if token.type == 'table_open' and token.map:
            start_line, end_line = token.map
            table_md = "\n".join(lines[start_line:end_line])
            tables.append(table_md)
    return tables

def unroll_single_table(md_content: str) -> str:
    """Converts a single markdown table into a structured key-value format."""
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_content)
    unrolled_content_parts = []
    headers = []
    in_header = False
    is_data_row = False

    for i, token in enumerate(tokens):
        if token.type == 'thead_open': in_header = True; continue
        if token.type == 'thead_close': in_header = False; continue
        if token.type == 'tbody_open': is_data_row = True; continue
        if token.type == 'tbody_close': is_data_row = False; continue

        if token.type == 'tr_open':
            row_cells = []
            j = i + 1
            while j < len(tokens) and tokens[j].type != 'tr_close':
                if tokens[j].type == 'inline':
                    row_cells.append(tokens[j].content.strip())
                j += 1

            if in_header:
                headers = row_cells
            elif is_data_row and headers and row_cells and any(cell for cell in row_cells):
                item_name = row_cells[0] if row_cells else ""
                if not item_name: continue
                unrolled_content_parts.append(f"\n### {item_name}\n")
                for header, cell in zip(headers, row_cells):
                    if header and cell and cell not in ['-', '']:
                        unrolled_content_parts.append(f"- **{header.strip()}**: {cell.strip()}\n")
    return "".join(unrolled_content_parts)

def unroll_changelog(md_content: str) -> str:
    """Parses a changelog file and unrolls its list items into headers without using an LLM."""
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_content)
    
    unrolled_parts = ["\n\n---\n\n## Unrolled Changelog Data"]
    current_version = ""
    list_level = 0

    for i, token in enumerate(tokens):
        if token.type == 'bullet_list_open':
            list_level += 1
        elif token.type == 'bullet_list_close':
            list_level -= 1
        elif token.type == 'list_item_open':
            item_content_token = tokens[i+2]
            if item_content_token.type == 'inline':
                item_content = item_content_token.content.strip()
                
                if list_level == 1:
                    current_version = item_content
                elif list_level == 2 and current_version:
                    unrolled_parts.append(f"\n### {current_version} - {item_content}\n")

    if len(unrolled_parts) > 1:
        return "".join(unrolled_parts)
    return ""

def summarize_and_enrich_content(md_content: str, file_path_for_logging: Path) -> str:
    """Orchestrates the summarization and enrichment process for a markdown file."""
    if is_changelog_file(file_path_for_logging, md_content):
        logger.info(f"Processing '{file_path_for_logging.name}' as a changelog file.")
        unrolled_changelog_content = unroll_changelog(md_content)
        return md_content + unrolled_changelog_content

    logger.info(f"Building section tree for {file_path_for_logging.name}...")
    document_tree = build_section_tree(md_content)

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

