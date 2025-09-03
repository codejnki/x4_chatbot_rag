# Makefile for both Windows and Unix-like systems

# Data files
ZIP_FILE := x4-foundations-wiki.zip
WIKI_DIR := x4-foundations-wiki
HASH_FILE := $(WIKI_DIR)/file_hashes.json

# --- Directories ---
SANITIZED_DIR := $(WIKI_DIR)/hashed_pages
MD_PAGES_DIR := $(WIKI_DIR)/pages_md
SUMMARIZED_PAGES_DIR := $(WIKI_DIR)/pages_summarized
KEYWORDS_CACHE_DIR := .keyword_cache

# --- Python Scripts ---
UNZIP_SCRIPT := 00_unzip_data.py
HTML_TO_MD_SCRIPT := 01a_html_to_md.py
SUMMARIZE_MD_SCRIPT := 01b_summarize_md.py
GET_FILES_TO_PROCESS_SCRIPT := 01c_get_files_to_process.py
CHUNK_SCRIPT := 02_chunk_corpus.py
VECTOR_STORE_SCRIPT := 03_build_vector_store.py
KEYWORDS_SCRIPT := 04_generate_keywords.py
REFINE_KEYWORDS_SCRIPT := 05_refine_keywords.py

# --- Generated Files ---
CHUNKS_FILE := x4_wiki_chunks.json
VECTOR_STORE_DIR := faiss_index
KEYWORDS_FILE := x4_keywords.json
REFINED_KEYWORDS_FILE := x4_keywords_refined.json

# Define the virtual environment directory
VENV_DIR := .venv

# OS-specific configuration
ifeq ($(OS),Windows_NT)
    PY := python
    VENV_PATH_DIR := Scripts
    RM_RF = cmd /c rmdir /s /q
    EXE := .exe
else
    PY := python3
    VENV_PATH_DIR := bin
    RM_RF = rm -rf
    EXE :=
endif

# Define the Python interpreter and pip from within the virtual environment
PYTHON := $(VENV_DIR)/$(VENV_PATH_DIR)/python$(EXE)
PIP := $(VENV_DIR)/$(VENV_PATH_DIR)/pip$(EXE)
VENV_TIMESTAMP := $(VENV_DIR)/.installed

# --- Main Targets ---
.DEFAULT_GOAL := run

.PHONY: data markdown summarize chunks vector-store keywords keywords-refined clean-all clean-hashed-html clean-md-pages clean-summarized-pages clean-chunks clean-vector-store clean-keywords-cache clean-keywords-files clean-venv freeze help all run install

# Run the entire pipeline and start the server
run: all
	@echo "--> Starting the FastAPI server..."
	$(PYTHON) main.py

# Build all data artifacts after ensuring dependencies are installed
all: $(VENV_TIMESTAMP) vector-store keywords-refined

# A phony target to make 'make install' user-friendly
install: $(VENV_TIMESTAMP)

# Install dependencies only if venv is new or requirements.txt has changed
$(VENV_TIMESTAMP): $(PIP) requirements.txt
	@echo "--> Installing/updating dependencies..."
	$(PIP) install -r requirements.txt
	touch $(VENV_TIMESTAMP)

# Create virtual environment if its pip executable doesn't exist
$(PIP):
	@echo "--> Creating virtual environment in $(VENV_DIR)..."
	$(PY) -m venv $(VENV_DIR)

# --- Data Pipeline ---

# Generate the final, refined keyword list.
keywords-refined: $(REFINED_KEYWORDS_FILE)
$(REFINED_KEYWORDS_FILE): keywords $(REFINE_KEYWORDS_SCRIPT)
	@echo "--> Refining keyword list..."
	$(PYTHON) $(REFINE_KEYWORDS_SCRIPT)

# Generate the raw keyword list from the chunks using an LLM.
keywords: $(KEYWORDS_FILE)
$(KEYWORDS_FILE): chunks $(KEYWORDS_SCRIPT)
	@echo "--> Generating keywords from chunks (this may take a long time)..."
	$(PYTHON) $(KEYWORDS_SCRIPT)

# Build the FAISS vector store from the chunks.
vector-store: $(VECTOR_STORE_DIR)
$(VECTOR_STORE_DIR): chunks $(VECTOR_STORE_SCRIPT)
	@echo "--> Building vector store from chunks..."
	$(PYTHON) $(VECTOR_STORE_SCRIPT)

# Create the chunked JSON file from the corpus.
chunks: summarize
	@echo "--> Chunking corpus file..."
	$(PYTHON) $(CHUNK_SCRIPT)

# Create the summarized markdown files.
summarize: markdown
	@echo "--> Summarizing markdown files..."
	@$(PYTHON) $(GET_FILES_TO_PROCESS_SCRIPT) $(MD_PAGES_DIR) $(SUMMARIZED_PAGES_DIR) .md .md | \
	xargs -P 8 -I {} $(PYTHON) $(SUMMARIZE_MD_SCRIPT) {}

# Create the markdown files from the sanitized html files.
markdown: data
	@echo "--> Converting HTML to Markdown..."
	@$(PYTHON) $(GET_FILES_TO_PROCESS_SCRIPT) $(SANITIZED_DIR) $(MD_PAGES_DIR) .html .md | \
	xargs -P 8 -I {} $(PYTHON) $(HTML_TO_MD_SCRIPT) {}

# Unzip the wiki data if the zip file has changed.
data: $(HASH_FILE)
$(HASH_FILE): $(ZIP_FILE) $(UNZIP_SCRIPT)
	@echo "--> Unzipping and sanitizing wiki data..."
	$(PYTHON) $(UNZIP_SCRIPT)

# --- Utility Targets ---

# Freeze dependencies
freeze: $(PIP)
	@echo "--> Freezing dependencies to requirements.txt..."
	$(PIP) freeze > requirements.txt

# Clean up the project
clean-all: clean-hashed-html clean-md-pages clean-summarized-pages clean-chunks clean-vector-store clean-keywords-cache clean-keywords-files
	@echo "--> Full cleanup complete."

clean-hashed-html:
	@echo "--> Deleting hashed html pages..."
	-$(RM_RF) $(SANITIZED_DIR)
	-rm -f $(HASH_FILE)

clean-md-pages:
	@echo "--> Deleting markdown pages..."
	-$(RM_RF) $(MD_PAGES_DIR)

clean-summarized-pages:
	@echo "--> Deleting summarized pages..."
	-$(RM_RF) $(SUMMARIZED_PAGES_DIR)

clean-chunks:
	@echo "--> Deleting chunks file..."
	-rm -f $(CHUNKS_FILE)

clean-vector-store:
	@echo "--> Deleting vector store..."
	-$(RM_RF) $(VECTOR_STORE_DIR)

clean-keywords-cache:
	@echo "--> Deleting keyword cache..."
	-$(RM_RF) $(KEYWORDS_CACHE_DIR)

clean-keywords-files:
	@echo "--> Deleting keyword files..."
	-rm -f $(KEYWORDS_FILE) $(REFINED_KEYWORDS_FILE)

# Deletes the virtual environment
clean-venv:
	@echo "--> Deleting virtual environment..."
	-$(RM_RF) $(VENV_DIR)
	@echo "--> Virtual environment deleted."

# Help
help:
	@echo "Available targets:"
	@echo "  run                   - (Default) Builds all data and starts the server."
	@echo "  all                   - Ensures dependencies are installed and builds all data artifacts."
	@echo "  install               - Ensures venv exists and all dependencies are installed."
	@echo "  data                  - Unzips the wiki data from $(ZIP_FILE)."
	@echo "  markdown              - Generates markdown files from html."
	@echo "  summarize             - Generates summarized markdown files."
	@echo "  chunks                - Generates the chunked JSON file for embedding."
	@echo "  vector-store          - Builds the FAISS vector store for the RAG model."
	@echo "  keywords              - Generates a raw list of keywords using an LLM."
	@echo "  keywords-refined      - Creates the final, cleaned list of keywords."
	@echo "  freeze                - Updates requirements.txt from the current environment."
	@echo "  clean-all             - Removes all generated data and caches."
	@echo "  clean-hashed-html     - Deletes the hashed html pages."
	@echo "  clean-md-pages        - Deletes the markdown pages."
	@echo "  clean-summarized-pages- Deletes the summarized pages."
	@echo "  clean-chunks          - Deletes the chunks file."
	@echo "  clean-vector-store    - Deletes the vector store."
	@echo "  clean-keywords-cache  - Deletes the keyword generation cache."
	@echo "  clean-keywords-files  - Deletes the keyword files."
	@echo "  clean-venv            - Deletes the Python virtual environment."
	@echo "  help                  - Shows this help message."