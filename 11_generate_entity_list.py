# 11_generate_entity_list.py

import json
import re
from pathlib import Path

def generate_entity_list(corpus_path="x4_wiki_corpus.json", output_path="x4_entities.json"):
    """
    Scans the entire wiki corpus (a JSON array of page objects) and extracts
    all unique page titles to serve as our list of in-game entities.
    """
    corpus_file = Path(corpus_path)
    if not corpus_file.exists():
        print(f"Error: Corpus file not found at {corpus_path}")
        return

    print(f"Loading corpus from {corpus_path}. This may take a moment...")
    with open(corpus_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Processing {len(data)} documents to extract entities...")
    
    entity_titles = set()
    for item in data:
        # Each item in the array is a dictionary representing a wiki page
        if isinstance(item, dict) and 'title' in item:
            title = item['title']
            
            # Perform a safe, minimal cleaning to remove wiki-style numerical prefixes.
            # e.g., "01 - Split Vendetta" becomes "Split Vendetta"
            # e.g., "1. X4 Foundations Wiki" becomes "X4 Foundations Wiki"
            # This makes the entity name more natural for matching in a sentence.
            cleaned_title = re.sub(r'^\s*\d+[\s.-]*\s*', '', title).strip()

            # Add the cleaned title to a set to automatically handle duplicates.
            if cleaned_title:
                entity_titles.add(cleaned_title)

    # Convert the set to a list and sort it alphabetically for a clean, readable output file.
    sorted_entities = sorted(list(entity_titles))

    output = {
        "description": "A comprehensive list of all unique page titles from the X4 Foundations wiki, serving as a keyword list for the RAG retriever.",
        "count": len(sorted_entities),
        "entities": sorted_entities
    }

    output_file = Path(output_path)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Successfully extracted {len(sorted_entities)} unique entities.")
    print(f"Entity list saved to {output_path}")

if __name__ == "__main__":
    generate_entity_list()
