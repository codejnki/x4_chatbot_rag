# Makefile for the X4 RAG Chatbot Data Pipeline

# --- Environment Setup ---
# Determines the Python executable and remove command based on the operating system.
ifeq ($(OS),Windows_NT)
    PYTHON      := python
    RM_RF       = cmd /c rd /s /q
else
    PYTHON      := python3
    RM_RF       = rm -rf
endif

# --- File & Directory Definitions ---
# Source Data
ZIP_FILE := x4-foundations-wiki.zip

# Output Directories
SANITIZED_DIR   := x4-foundations-wiki/hashed_pages
MD_PAGES_DIR    := x4-foundations-wiki/pages_md

# Timestamp files to track step completion
UNZIP_TIMESTAMP     := $(SANITIZED_DIR)/.unzipped
MARKDOWN_TIMESTAMP  := $(MD_PAGES_DIR)/.processed

# --- Phony Targets ---
.PHONY: all data markdown clean-all clean-data clean-markdown

# --- Main Targets ---
all: markdown

# 2. HTML to Markdown
# Converts HTML files to markdown in parallel, processing only new or updated files.
markdown: $(MARKDOWN_TIMESTAMP)

$(MARKDOWN_TIMESTAMP): $(UNZIP_TIMESTAMP) 01a_html_to_md.py 01c_get_files_to_process.py
	@echo "--> Converting HTML to Markdown (in parallel)..."
	@$(PYTHON) 01c_get_files_to_process.py $(SANITIZED_DIR) $(MD_PAGES_DIR) .html .md | xargs -P 8 -I {} $(PYTHON) 01a_html_to_md.py {}
	@touch $(MARKDOWN_TIMESTAMP)

# 1. Data Unzip
# Unzips the wiki data if the source zip or the script is newer.
data: $(UNZIP_TIMESTAMP)

$(UNZIP_TIMESTAMP): $(ZIP_FILE) 00_unzip_data.py
	@echo "--> Unzipping and sanitizing wiki data..."
	@$(PYTHON) 00_unzip_data.py
	@touch $(UNZIP_TIMESTAMP)

# --- Clean Targets ---
clean-all: clean-data clean-markdown

# Deletes the generated markdown pages.
clean-markdown:
	@echo "--> Deleting markdown pages..."
ifeq ($(OS),Windows_NT)
	-$(RM_RF) $(subst /,\,$(MD_PAGES_DIR))
else
	-$(RM_RF) $(MD_PAGES_DIR)
endif

# Deletes all of the unpacked HTML files.
clean-data:
	@echo "--> Deleting sanitized HTML data..."
ifeq ($(OS),Windows_NT)
	-$(RM_RF) $(subst /,\,$(SANITIZED_DIR))
else
	-$(RM_RF) $(SANITIZED_DIR)
endif