# 13_refine_keyword_list.py

import json
from pathlib import Path

# --- Configuration ---
INPUT_KEYWORDS_FILE = "x4_keywords.json"
OUTPUT_KEYWORDS_FILE = "x4_keywords_refined.json"

# A list of common English words (stop words) that are highly likely to be false positives.
STOP_WORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 
    'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 
    'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 
    'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 
    'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 
    'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 
    'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 
    'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 
    'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 
    'don', 'should', 'now', 'ai' # Added 'ai' as it's too generic
}

def refine_keywords():
    """
    Loads the generated keyword list and applies a series of filters to
    remove noise, stop words, and non-entity-like terms.
    """
    print("--- Starting Keyword Refinement ---")
    
    # 1. Load the raw keywords
    try:
        with open(INPUT_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        raw_keywords = data.get('keywords', [])
        print(f"Loaded {len(raw_keywords)} raw keywords from '{INPUT_KEYWORDS_FILE}'.")
    except FileNotFoundError:
        print(f"Error: Input file not found at '{INPUT_KEYWORDS_FILE}'.")
        return

    # 2. Apply a series of filtering rules
    refined_keywords = set()
    for keyword in raw_keywords:
        kw_lower = keyword.lower()
        
        # Rule 1: Must be at least 3 characters long (removes "I", etc.)
        if len(kw_lower) < 3:
            continue
            
        # Rule 2: Must not be a common stop word
        if kw_lower in STOP_WORDS:
            continue
            
        # Rule 3: Must not contain special characters likely from code/variables
        if any(char in keyword for char in ['$', '*', '<', '>', '{', '}']):
            continue

        # Rule 4: Must contain at least one letter (removes purely numerical keywords)
        if not any(char.isalpha() for char in keyword):
            continue
            
        refined_keywords.add(keyword)

    sorted_keywords = sorted(list(refined_keywords))
    print(f"Refined list down to {len(sorted_keywords)} high-quality keywords.")

    # 3. Save the new, clean list
    output_data = {
        "description": "A refined list of keywords, filtered to remove noise and common words.",
        "count": len(sorted_keywords),
        "keywords": sorted_keywords
    }
    with open(OUTPUT_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
        
    print(f"Saved refined keyword list to '{OUTPUT_KEYWORDS_FILE}'.")
    print("--- Refinement Complete ---")

if __name__ == "__main__":
    refine_keywords()
