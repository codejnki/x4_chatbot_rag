# 05_refine_keywords.py

import json
import logging
from pathlib import Path
from tqdm import tqdm

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
INPUT_KEYWORDS_FILE = "x4_keywords.json"
OUTPUT_KEYWORDS_FILE = "x4_keywords_refined.json"

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
    'don', 'should', 'now', 'ai'
}

def refine_keywords():
    """
    Loads the generated keyword list and applies a series of filters to
    remove noise, stop words, and non-entity-like terms.
    """
    logger.info("--- Starting Phase 5: Keyword Refinement ---")
    
    try:
        with open(INPUT_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        raw_keywords = data.get('keywords', [])
        logger.info(f"Loaded {len(raw_keywords)} raw keywords from '{INPUT_KEYWORDS_FILE}'.")
    except FileNotFoundError:
        logger.error(f"Input file not found at '{INPUT_KEYWORDS_FILE}'.")
        return

    refined_keywords = set()
    for keyword in tqdm(raw_keywords, desc="Refining keywords"):
        kw_lower = keyword.lower()
        
        if len(kw_lower) < 3:
            continue
        if kw_lower in STOP_WORDS:
            continue
        if any(char in keyword for char in ['$', '*', '<', '>', '{', '}']):
            continue
        if not any(char.isalpha() for char in keyword):
            continue
        refined_keywords.add(keyword)

    sorted_keywords = sorted(list(refined_keywords))
    logger.info(f"Refined list down to {len(sorted_keywords)} high-quality keywords.")

    output_data = {
        "description": "A refined list of keywords, filtered to remove noise and common words.",
        "count": len(sorted_keywords),
        "keywords": sorted_keywords
    }
    with open(OUTPUT_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
        
    logger.info(f"Saved refined keyword list to '{OUTPUT_KEYWORDS_FILE}'.")
    logger.info("--- Refinement Complete ---")

if __name__ == "__main__":
    refine_keywords()