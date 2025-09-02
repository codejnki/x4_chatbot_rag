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

# Define the virtual environment directory
VENV_DIR := .venv

# OS-specific configuration
ifeq ($(OS),Windows_NT)
    # Windows settings
    PY := python
    VENV_PATH_DIR := Scripts
    ACTIVATE_CMD := .\\$(VENV_DIR)\\Scripts\\activate
    RM_RF = cmd /c rmdir /s /q
    # Use 7-Zip on Windows to handle long file paths.
    UNZIP_CMD = 7z x $(ZIP_FILE) -o$(WIKI_DIR) pages -y
else
    # Unix-like (Linux, macOS) settings
    PY := python3
    VENV_PATH_DIR := bin
    ACTIVATE_CMD := source $(VENV_DIR)/bin/activate
    RM_RF = rm -rf
    UNZIP_CMD = unzip -oq $(ZIP_FILE) 'pages/*' -d $(WIKI_DIR)
endif

# Define the Python interpreter from within the virtual environment
PYTHON := $(VENV_DIR)/$(VENV_PATH_DIR)/python
PIP := $(VENV_DIR)/$(VENV_PATH_DIR)/pip

# Define the requirements file
REQUIREMENTS := requirements.txt

# --- Targets ---

# By default, running 'make' will run the 'install' target
.DEFAULT_GOAL := install

# Phony targets are not files.
.PHONY: install venv data clean freeze help

# Install dependencies
install: venv
	@echo "--> Installing dependencies from $(REQUIREMENTS)..."
	$(PIP) install -r $(REQUIREMENTS)
	@echo "--> Dependencies installed successfully."

# Create virtual environment if it doesn't exist
venv: $(PIP)
$(PIP):
	@echo "--> Creating virtual environment in $(VENV_DIR)..."
	$(PY) -m venv $(VENV_DIR)
	@echo "--> Virtual environment created."
	@echo "--> To activate it, run: $(ACTIVATE_CMD)"

# --- Data Pipeline ---

# Build the FAISS vector store from the chunks.
vector-store: $(VECTOR_STORE_DIR)
$(VECTOR_STORE_DIR): $(CHUNKS_FILE) $(VECTOR_STORE_SCRIPT)
	@echo "--> Building vector store from chunks..."
	$(PYTHON) $(VECTOR_STORE_SCRIPT)
	@echo "--> Vector store is up to date."

# Create the chunked JSON file from the corpus.
chunks: $(CHUNKS_FILE)
$(CHUNKS_FILE): $(CORPUS_FILE) $(CHUNK_SCRIPT)
	@echo "--> Chunking corpus file..."
	$(PYTHON) $(CHUNK_SCRIPT)
	@echo "--> Chunks file '$(CHUNKS_FILE)' is up to date."

# Create the JSON corpus from the HTML files.
corpus: $(CORPUS_FILE)
$(CORPUS_FILE): $(PAGES_DIR) $(CORPUS_SCRIPT)
	@echo "--> Generating wiki corpus from HTML files..."
	$(PYTHON) $(CORPUS_SCRIPT)
	@echo "--> Corpus file '$(CORPUS_FILE)' is up to date."

# Unzip the wiki data.
data: $(PAGES_DIR)
$(PAGES_DIR): $(ZIP_FILE)
	@echo "--> Unzipping wiki data from $(ZIP_FILE)..."
	$(UNZIP_CMD)
	@echo "--> Wiki data is ready."

# --- Utility Targets ---

# Freeze dependencies
freeze: venv
	@echo "--> Freezing dependencies to $(REQUIREMENTS)..."
	$(PIP) freeze > $(REQUIREMENTS)
	@echo "--> requirements.txt has been updated."

# Clean up the project
clean:
	@echo "--> Cleaning up..."
	-$(RM_RF) $(VENV_DIR)
	-$(RM_RF) $(WIKI_DIR)
	-$(RM_RF) $(CORPUS_FILE) $(CHUNKS_FILE)
	-$(RM_RF) $(VECTOR_STORE_DIR)
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "--> Cleanup complete."

# Help
help:
	@echo "Available targets:"
	@echo "  install      - (Default) Creates venv and installs dependencies."
	@echo "  vector-store - Builds the FAISS vector store for the RAG model."
	@echo "  chunks       - Generates the chunked JSON file for embedding."
	@echo "  corpus       - Generates the JSON corpus from the wiki data."
	@echo "  data         - Unzips the wiki data from $(ZIP_FILE)."
	@echo "  venv         - Creates the virtual environment."
	@echo "  freeze       - Updates requirements.txt from the current environment."
	@echo "  clean        - Removes the venv, data, and all generated files."
	@echo "  help         - Shows this help message."