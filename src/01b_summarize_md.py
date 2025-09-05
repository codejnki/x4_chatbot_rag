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

def strip_until_newline(text: str) -> str:
    return re.sub(r'^.*\n', '', text, count=1)

def call_summarizer(content: str, task: str, context_path: str) -> str:
    try:
        if not content:
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
    
    # Stores the start line for the content of the current section
    last_line = 0

    for i, token in enumerate(tokens):
        if token.type == 'heading_open':
            # 1. Finalize the content of the PREVIOUS section
            # The content ends on the line just before the new heading starts.
            # token.map provides the [start_line, end_line] for the heading element.
            current_heading_start_line = token.map[0]
            
            # Slice the original document lines to get the content
            content_lines = lines[last_line:current_heading_start_line]
            node_stack[-1].content = "\n".join(content_lines).strip()

            # The content for the NEXT section starts after this heading ends.
            last_line = token.map[1]

            # 2. Create and place the new section node
            level = int(token.tag[1:])
            title = tokens[i+1].content.strip() if (i+1) < len(tokens) else ""
            new_node = Section(title=title, level=level)

            while node_stack[-1].level >= level:
                node_stack.pop()
            
            parent = node_stack[-1]
            parent.children.append(new_node)
            new_node.parent = parent
            node_stack.append(new_node)

    # After the loop, capture the remaining content for the very last section
    if last_line < len(lines):
        content_lines = lines[last_line:]
        node_stack[-1].content = "\n".join(content_lines).strip()
    
    return root

def summarize_tree_post_order(node: Section, context_path: str = ""):
    """Recursively summarizes the tree from the bottom up (post-order traversal)."""
    # Root node has special handling for context
    if node.level == 0:
        # Try to find a document title from the first H1
        first_h1 = next((child for child in node.children if child.level == 1), None)
        if first_h1:
             context_path = first_h1.title
        else:
            # Fallback for documents without an H1
             context_path = "Document Overview"
    for child in node.children:
        child_context_path = f"{context_path} > {child.title}"
        summarize_tree_post_order(child, child_context_path)

    # For parent nodes, combine their content with the summaries of their children
    child_summaries = "".join([f"Sub-section '{c.title}': {c.summary}" for c in node.children if c.summary])

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
        summary_text = recursive_summarize(texts, "SUMMARIZE_SECTION", context_path=context_path)
    else:
        summary_text = call_summarizer(content_to_summarize, "SUMMARIZE_SECTION", context_path=context_path)

    node.summary = summary_text
    
    # CORRECTED LOGIC: Find all tables, unroll each one individually,
    # and append them to the summary in a structured format.
    section_tables = find_all_tables_in_md(node.content)
    if section_tables:
        all_unrolled_content = ["\n\n---\n\n## Unrolled Table Data"]
        for i, table_md in enumerate(section_tables):
            # Pass each individual 'table_md' to the unroller
            unrolled_table = unroll_single_table(table_md)
            if unrolled_table:
                all_unrolled_content.append(f"\n\n**Table {i+1}**")
                all_unrolled_content.append(unrolled_table)
        
        # Append the final, combined string to the summary
        if len(all_unrolled_content) > 1:
             node.summary += "".join(all_unrolled_content)

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

def find_all_tables_in_md(md_content: str) -> List[str]:
    """
    Finds all complete Markdown tables in a string using the MarkdownIt parser's
    token stream. This version directly uses the map from the 'table_open' token.
    """
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_content)
    lines = md_content.splitlines()
    
    tables = []

    # We can simplify the loop to only look for the opening token.
    for token in tokens:
        if token.type == 'table_open':
            # The 'map' attribute on the opening token contains [start_line, end_line]
            # for the entire table block. It's all we need.
            if token.map:
                start_line, end_line = token.map
                
                # Slice the original lines to reconstruct the table markdown
                table_md = "\n".join(lines[start_line:end_line])
                tables.append(table_md)
            
    return tables

def unroll_single_table(md_content: str) -> str:
    """
    Takes the markdown for a single table and converts it into a
    structured key-value format.
    """
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_content)

    unrolled_content_parts = []
    in_header = False
    headers = []
    is_data_row = False

    for i, token in enumerate(tokens):
        if token.type == 'thead_open': in_header = True; continue
        if token.type == 'thead_close': in_header = False; continue
        if token.type == 'tbody_open': is_data_row = True; continue
        if token.type == 'tbody_close': is_data_row = False; continue

        if token.type == 'tr_open':
            row_cells = []
            j = i + 1
            # Gather all inline content tokens until the row closes
            while j < len(tokens) and tokens[j].type != 'tr_close':
                if tokens[j].type == 'inline':
                    row_cells.append(tokens[j].content.strip())
                j += 1

            if in_header:
                headers = row_cells
            elif is_data_row and headers and row_cells and any(cell for cell in row_cells):
                # Use the first cell as the item name
                item_name = row_cells[0] if row_cells else ""
                if not item_name: continue

                unrolled_content_parts.append(f"\n### {item_name}\n")

                # Zip headers and cells to create key-value pairs
                for header, cell in zip(headers, row_cells):
                    if header and cell and cell not in ['-', '']:
                        unrolled_content_parts.append(f"- **{header.strip()}**: {cell.strip()}\n")

    return "".join(unrolled_content_parts)

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

    logger.info(input_file_path)
    logger.info(output_file_path)

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



