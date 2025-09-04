# Makefile for the X4 RAG Chatbot Data Pipeline
# This version uses a strict file-based dependency chain to prevent unnecessary rebuilds.

# --- OS & Environment Setup ---
VENV_DIR := .venv

# OS-specific configuration for Python executable and virtual environment paths
ifeq ($(OS),Windows_NT)
    PY := python
    VENV_PATH_DIR := Scripts
    RM_RF = cmd /c rd /s /q
    EXE := .exe
else
    PY := python3
    VENV_PATH_DIR := bin
    RM_RF = rm -rf
    EXE :=
endif

PYTHON := $(VENV_DIR)/$(VENV_PATH_DIR)/python$(EXE)
PIP := $(VENV_DIR)/$(VENV_PATH_DIR)/pip$(EXE)
VENV_TIMESTAMP := $(VENV_DIR)/.installed

# --- File & Directory Definitions ---
# Source Data
ZIP_FILE := x4-foundations-wiki.zip

# Intermediate Directories
WIKI_DIR := x4-foundations-wiki
SANITIZED_DIR := $(WIKI_DIR)/hashed_pages
MD_PAGES_DIR := $(WIKI_DIR)/pages_md
SUMMARIZED_PAGES_DIR := $(WIKI_DIR)/pages_summarized
VECTOR_STORE_DIR := faiss_index
KEYWORDS_CACHE_DIR := .keyword_cache

# Final Data Artifacts
HASH_FILE := $(WIKI_DIR)/file_hashes.json
SUMMARIZED_PAGES_TIMESTAMP := $(SUMMARIZED_PAGES_DIR)/.processed
WIKI_CHUNKS_FILE := x4_wiki_chunks.json
CHANGELOG_CHUNKS_FILE := x4_changelog_chunks.json
ALL_CHUNKS_FILE := x4_all_chunks.json
VECTOR_STORE_TIMESTAMP := $(VECTOR_STORE_DIR)/.processed
KEYWORDS_FILE := x4_keywords.json
REFINED_KEYWORDS_FILE := x4_keywords_refined.json
KEYWORDS_TIMESTAMP := $(KEYWORDS_CACHE_DIR)/.processed

# --- Main Targets ---
.DEFAULT_GOAL := run

# Phony targets do not represent files and should always run.
.PHONY: all run install freeze help clean clean-data clean-md clean-summaries clean-chunks clean-vector-store clean-keywords clean-venv

# The 'all' target is the main entry point for building data.
all: $(REFINED_KEYWORDS_FILE) $(VECTOR_STORE_TIMESTAMP)

# The 'run' target builds everything and then starts the server.
run: all
	@echo "--> Starting the FastAPI server..."
	$(PYTHON) main.py

# The 'install' target sets up the virtual environment and dependencies.
install: $(VENV_TIMESTAMP)

# --- Dependency Installation ---
$(VENV_TIMESTAMP): requirements.txt $(PIP)
	@echo "--> Installing/updating dependencies..."
	$(PIP) install -r requirements.txt
	@touch $(VENV_TIMESTAMP)

$(PIP):
	@echo "--> Creating virtual environment in $(VENV_DIR)..."
	$(PY) -m venv $(VENV_DIR)

# --- Data Pipeline (File-Based Dependencies) ---

# 7. Refine Keywords: Depends on the raw keywords file.
$(REFINED_KEYWORDS_FILE): $(KEYWORDS_FILE) 05_refine_keywords.py
	@echo "--> Refining keyword list..."
	@$(PYTHON) 05_refine_keywords.py

# 6. Generate Raw Keywords: Depends on the vector store being complete.
$(KEYWORDS_FILE): $(KEYWORDS_TIMESTAMP)

$(KEYWORDS_TIMESTAMP): $(VECTOR_STORE_TIMESTAMP) 04_generate_keywords.py
	@echo "--> Generating keywords from chunks (this may take a long time)..."
	@$(PYTHON) 04_generate_keywords.py
	@touch $(KEYWORDS_TIMESTAMP)

# 5. Build Vector Store: Depends on the merged chunks file.
$(VECTOR_STORE_TIMESTAMP): $(ALL_CHUNKS_FILE) 03_build_vector_store.py
	@echo "--> Building vector store from all chunks..."
	@$(PYTHON) 03_build_vector_store.py
	@touch $(VECTOR_STORE_TIMESTAMP)

# 4. Merge Chunks: Depends on both the wiki chunks and the changelog chunks.
$(ALL_CHUNKS_FILE): $(WIKI_CHUNKS_FILE) $(CHANGELOG_CHUNKS_FILE) 02b_merge_chunks.py
	@echo "--> Merging wiki and changelog chunk files..."
	@$(PYTHON) 02b_merge_chunks.py

# 3b. Process Changelogs: Depends on the markdown files being generated.
$(CHANGELOG_CHUNKS_FILE): $(SUMMARIZED_PAGES_TIMESTAMP) 01d_process_changelogs.py
	@echo "--> Processing changelogs into structured chunks..."
	@$(PYTHON) 01d_process_changelogs.py

# 3a. Chunk Wiki Corpus: Depends on the summarized markdown files.
$(WIKI_CHUNKS_FILE): $(SUMMARIZED_PAGES_TIMESTAMP) 02_chunk_corpus.py
	@echo "--> Chunking summarized wiki files..."
	@$(PYTHON) 02_chunk_corpus.py

# 2. Summarize Markdown: This is a complex step. It depends on the existence of markdown files.
# We use a timestamp file to track completion because it processes a whole directory.
$(SUMMARIZED_PAGES_TIMESTAMP): $(HASH_FILE) 01b_summarize_md.py 01a_html_to_md.py 01c_get_files_to_process.py
	@echo "--> Converting HTML to Markdown..."
	@$(PYTHON) 01c_get_files_to_process.py $(SANITIZED_DIR) $(MD_PAGES_DIR) .html .md | xargs -P 8 -I {} $(PYTHON) 01a_html_to_md.py {}
	@echo "--> Summarizing markdown files..."
	@PROCESS_LIST=$($(PYTHON) 01c_get_files_to_process.py $(MD_PAGES_DIR) $(SUMMARIZED_PAGES_DIR) .md .md); \
	if [ -n "$$PROCESS_LIST" ]; then \
		echo "$$PROCESS_LIST" | xargs -P 4 -I {} $(PYTHON) 01b_summarize_md.py {}; \
	fi
	@touch $(SUMMARIZED_PAGES_TIMESTAMP)

# 1. Unzip Data: The first step, depends on the zip file.
$(HASH_FILE): $(ZIP_FILE) 00_unzip_data.py
	@echo "--> Unzipping and sanitizing wiki data..."
	@$(PYTHON) 00_unzip_data.py

# --- Utility Targets ---
freeze:
	@echo "--> Freezing dependencies to requirements.txt..."
	$(PIP) freeze > requirements.txt

help:
	@echo "Available targets:"
	@echo "  run                   - (Default) Builds all data and starts the server."
	@echo "  all                   - Ensures dependencies are installed and builds all data artifacts."
	@echo "  install               - Ensures venv exists and all dependencies are installed."
	@echo "  freeze                - Updates requirements.txt from the current environment."
	@echo "  clean                 - Removes all generated data and caches."
	@echo "  clean-data            - Deletes the unzipped and sanitized wiki data."
	@echo "  clean-md              - Deletes the generated markdown pages."
	@echo "  clean-summaries       - Deletes the summarized markdown pages."
	@echo "  clean-chunks          - Deletes all chunk files."
	@echo "  clean-vector-store    - Deletes the vector store."
	@echo "  clean-keywords        - Deletes the keyword files and cache."
	@echo "  clean-venv            - Deletes the Python virtual environment."
	@echo "  help                  - Shows this help message."

# --- Clean Targets ---
clean: clean-data clean-md clean-summaries clean-chunks clean-vector-store clean-keywords
	@echo "--> Full cleanup complete."

clean-data:
	@echo "--> Deleting sanitized wiki data..."
	-$(RM_RF) $(SANITIZED_DIR)
	-$(RM_RF) $(HASH_FILE)
	-$(RM_RF) $(WIKI_DIR)/path_map.json

clean-md:
	@echo "--> Deleting markdown pages..."
	-$(RM_RF) $(MD_PAGES_DIR)

clean-summaries:
	@echo "--> Deleting summarized pages..."
	-$(RM_RF) $(SUMMARIZED_PAGES_DIR)

clean-chunks:
	@echo "--> Deleting all chunk files..."
	-$(RM_RF) $(WIKI_CHUNKS_FILE) $(CHANGELOG_CHUNKS_FILE) $(ALL_CHUNKS_FILE)

clean-vector-store:
	@echo "--> Deleting vector store..."
	-$(RM_RF) $(VECTOR_STORE_DIR)

clean-keywords:
	@echo "--> Deleting keyword files and cache..."
	-$(RM_RF) $(KEYWORDS_CACHE_DIR)
	-$(RM_RF) $(KEYWORDS_FILE)
	-$(RM_RF) $(REFINED_KEYWORDS_FILE)

clean-venv:
	@echo "--> Deleting virtual environment..."
	-$(RM_RF) $(VENV_DIR)