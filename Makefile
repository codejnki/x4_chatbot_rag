# Makefile for both Windows and Unix-like systems

# Data files
ZIP_FILE := x4-foundations-wiki.zip
WIKI_DIR := x4-foundations-wiki
PAGES_DIR := $(WIKI_DIR)/pages

# Python scripts and generated files
CORPUS_SCRIPT := 01_generate_corpus.py
CORPUS_FILE := x4_wiki_corpus.json
CHUNK_SCRIPT := 02_chunk_corpus.py
CHUNKS_FILE := x4_wiki_chunks.json
VECTOR_STORE_SCRIPT := 03_build_vector_store.py
VECTOR_STORE_DIR := faiss_index
KEYWORDS_SCRIPT := 04_generate_keywords.py
KEYWORDS_FILE := x4_keywords.json
KEYWORDS_CACHE_DIR := .keyword_cache
REFINE_KEYWORDS_SCRIPT := 05_refine_keywords.py
REFINED_KEYWORDS_FILE := x4_keywords_refined.json

# Define the virtual environment directory
VENV_DIR := .venv

# OS-specific configuration
ifeq ($(OS),Windows_NT)
    PY := python
    VENV_PATH_DIR := Scripts
    UNZIP_CMD = 7z x $(ZIP_FILE) -o$(WIKI_DIR) pages -y
    RM_RF = cmd /c rmdir /s /q
    EXE := .exe
else
    PY := python3
    VENV_PATH_DIR := bin
    UNZIP_CMD = unzip -oq $(ZIP_FILE) 'pages/*' -d $(WIKI_DIR)
    RM_RF = rm -rf
    EXE :=
endif

# Define the Python interpreter and pip from within the virtual environment
PYTHON := $(VENV_DIR)/$(VENV_PATH_DIR)/python$(EXE)
PIP := $(VENV_DIR)/$(VENV_PATH_DIR)/pip$(EXE)
VENV_TIMESTAMP := $(VENV_DIR)/.installed

# --- Main Targets ---
.DEFAULT_GOAL := run

.PHONY: data clean clean-keywords clean-venv freeze help all run install

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
$(REFINED_KEYWORDS_FILE): $(KEYWORDS_FILE) $(REFINE_KEYWORDS_SCRIPT)
	@echo "--> Refining keyword list..."
	$(PYTHON) $(REFINE_KEYWORDS_SCRIPT)

# Generate the raw keyword list from the chunks using an LLM.
keywords: $(KEYWORDS_FILE)
$(KEYWORDS_FILE): $(CHUNKS_FILE) $(KEYWORDS_SCRIPT)
	@echo "--> Generating keywords from chunks (this may take a long time)..."
	$(PYTHON) $(KEYWORDS_SCRIPT)

# Build the FAISS vector store from the chunks.
vector-store: $(VECTOR_STORE_DIR)
$(VECTOR_STORE_DIR): $(CHUNKS_FILE) $(VECTOR_STORE_SCRIPT)
	@echo "--> Building vector store from chunks..."
	$(PYTHON) $(VECTOR_STORE_SCRIPT)

# Create the chunked JSON file from the corpus.
chunks: $(CHUNKS_FILE)
$(CHUNKS_FILE): $(CORPUS_FILE) $(CHUNK_SCRIPT)
	@echo "--> Chunking corpus file..."
	$(PYTHON) $(CHUNK_SCRIPT)

# Create the JSON corpus from the HTML files.
corpus: $(CORPUS_FILE)
$(CORPUS_FILE): $(PAGES_DIR) $(CORPUS_SCRIPT)
	@echo "--> Generating wiki corpus from HTML files..."
	$(PYTHON) $(CORPUS_SCRIPT)

# Unzip the wiki data.
data: $(PAGES_DIR)
$(PAGES_DIR): $(ZIP_FILE)
	@echo "--> Unzipping wiki data from $(ZIP_FILE)..."
	$(UNZIP_CMD)

# --- Utility Targets ---

# Freeze dependencies
freeze: $(PIP)
	@echo "--> Freezing dependencies to requirements.txt..."
	$(PIP) freeze > requirements.txt

# Clean up the project
clean:
	@echo "--> Cleaning up project files (venv and keyword cache are preserved)..."
	-$(RM_RF) $(WIKI_DIR)
	-rm -f $(CORPUS_FILE) $(CHUNKS_FILE) $(KEYWORDS_FILE) $(REFINED_KEYWORDS_FILE)
	-$(RM_RF) $(VECTOR_STORE_DIR)
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "--> Cleanup complete."

# Clean the keyword cache specifically
clean-keywords:
	@echo "--> Deleting keyword cache..."
	-$(RM_RF) $(KEYWORDS_CACHE_DIR)
	@echo "--> Keyword cache deleted."

# Deletes the virtual environment
clean-venv:
	@echo "--> Deleting virtual environment..."
	-$(RM_RF) $(VENV_DIR)
	@echo "--> Virtual environment deleted."

# Help
help:
	@echo "Available targets:"
	@echo "  run               - (Default) Builds all data and starts the server."
	@echo "  all               - Ensures dependencies are installed and builds all data artifacts."
	@echo "  install           - Ensures venv exists and all dependencies are installed."
	@echo "  keywords-refined  - Creates the final, cleaned list of keywords."
	@echo "  keywords          - Generates a raw list of keywords using an LLM."
	@echo "  vector-store      - Builds the FAISS vector store for the RAG model."
	@echo "  chunks            - Generates the chunked JSON file for embedding."
	@echo "  corpus            - Generates the JSON corpus from the wiki data."
	@echo "  data              - Unzips the wiki data from $(ZIP_FILE)."
	@echo "  freeze            - Updates requirements.txt from the current environment."
	@echo "  clean             - Removes data and generated files (preserves venv and keyword cache)."
	@echo "  clean-keywords    - Deletes the keyword generation cache for a full rebuild."
	@echo "  clean-venv        - Deletes the Python virtual environment."
	@echo "  help              - Shows this help message."