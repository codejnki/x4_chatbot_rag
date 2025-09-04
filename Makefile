# Makefile for the X-Universe Data Extraction Pipeline

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

# Prompts
SUMMARIZER_PROMPT := prompts/document_summarizer_prompt.txt
CHANGELOG_PROMPT  := prompts/changelog_analyzer_prompt.txt

# Output Directories
SANITIZED_DIR           := x4-foundations-wiki/hashed_pages
MD_PAGES_DIR            := x4-foundations-wiki/pages_md
SUMMARIZED_PAGES_DIR    := x4-foundations-wiki/pages_summarized
VECTOR_STORE_DIR        := faiss_index

# Data Artifacts
CHANGELOG_CHUNKS_FILE   := x4_changel_chunks.json
WIKI_CHUNKS_FILE        := x4_wiki_chunks.json
ALL_CHUNKS_FILE         := x4_all_chunks.json

# Timestamp files to track step completion
UNZIP_TIMESTAMP         := $(SANITIZED_DIR)/.unzipped
MARKDOWN_TIMESTAMP      := $(MD_PAGES_DIR)/.processed
SUMMARIES_TIMESTAMP     := $(SUMMARIZED_PAGES_DIR)/.processed
VECTOR_STORE_TIMESTAMP  := $(VECTOR_STORE_DIR)/.processed

# --- Phony Targets ---
.PHONY: all data markdown markdown-summaries changelog-chunks wiki-chunks merged-chunks vector-store clean-all clean-data clean-markdown clean-markdown-summaries clean-changelog-chunks clean-wiki-chunks clean-merged-chunks clean-vector-store

# --- Main Targets ---
all: data markdown markdown-summaries changelog-chunks wiki-chunks merged-chunks vector-store

# 7. Build Vector Store
# Creates a FAISS vector store from the merged chunks.
vector-store: $(VECTOR_STORE_TIMESTAMP)

$(VECTOR_STORE_TIMESTAMP): $(ALL_CHUNKS_FILE) 03_build_vector_store.py
	@echo "--> Building vector store from all chunks..."
	@$(PYTHON) 03_build_vector_store.py
	@touch $(VECTOR_STORE_TIMESTAMP)

# 6. Merge Chunks
# Combines the wiki and changelog chunks into a single file.
merged-chunks: $(ALL_CHUNKS_FILE)

$(ALL_CHUNKS_FILE): $(WIKI_CHUNKS_FILE) $(CHANGELOG_CHUNKS_FILE) 02b_merge_chunks.py
	@echo "--> Merging wiki and changelog chunk files..."
	@$(PYTHON) 02b_merge_chunks.py

# 5. Chunk Wiki Corpus
# Breaks down the summarized markdown files into smaller, manageable chunks.
wiki-chunks: $(WIKI_CHUNKS_FILE)

$(WIKI_CHUNKS_FILE): $(SUMMARIES_TIMESTAMP) 02_chunk_corpus.py
	@echo "--> Chunking summarized wiki files..."
	@$(PYTHON) 02_chunk_corpus.py

# 4. Process Changelogs
# Extracts and structures data from changelog markdown files.
changelog-chunks: $(CHANGELOG_CHUNKS_FILE)

$(CHANGELOG_CHUNKS_FILE): $(MARKDOWN_TIMESTAMP) 01d_process_changelogs.py $(CHANGELOG_PROMPT)
	@echo "--> Processing changelogs into structured chunks..."
	@$(PYTHON) 01d_process_changelogs.py

# 3. Summarize Markdown
# Enriches markdown files with LLM-generated summaries.
markdown-summaries: $(SUMMARIES_TIMESTAMP)

$(SUMMARIES_TIMESTAMP): $(MARKDOWN_TIMESTAMP) 01b_summarize_md.py 01c_get_files_to_process.py $(SUMMARIZER_PROMPT)
	@echo "--> Summarizing markdown files (in parallel)..."
	@$(PYTHON) 01c_get_files_to_process.py $(MD_PAGES_DIR) $(SUMMARIZED_PAGES_DIR) .md .md | xargs -P 4 -I {} $(PYTHON) 01b_summarize_md.py {}
	@touch $(SUMMARIES_TIMESTAMP)

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
clean-all: clean-data clean-markdown clean-markdown-summaries clean-changelog-chunks clean-wiki-chunks clean-merged-chunks clean-vector-store

# Deletes the vector store.
clean-vector-store:
	@echo "--> Deleting vector store..."
ifeq ($(OS),Windows_NT)
	-$(RM_RF) $(subst /,\,$(VECTOR_STORE_DIR))
else
	-$(RM_RF) $(VECTOR_STORE_DIR)
endif

# Deletes the merged chunks file.
clean-merged-chunks:
	@echo "--> Deleting merged chunks..."
ifeq ($(OS),Windows_NT)
	-del $(subst /,\,$(ALL_CHUNKS_FILE))
else
	-$(RM_RF) $(ALL_CHUNKS_FILE)
endif

# Deletes the generated wiki chunks file.
clean-wiki-chunks:
	@echo "--> Deleting wiki chunks..."
ifeq ($(OS),Windows_NT)
	-del $(subst /,\,$(WIKI_CHUNKS_FILE))
else
	-$(RM_RF) $(WIKI_CHUNKS_FILE)
endif

# Deletes the generated changelog chunks file.
clean-changelog-chunks:
	@echo "--> Deleting changelog chunks..."
ifeq ($(OS),Windows_NT)
	-del $(subst /,\,$(CHANGELOG_CHUNKS_FILE))
else
	-$(RM_RF) $(CHANGELOG_CHUNKS_FILE)
endif

# Deletes the summarized markdown pages.
clean-markdown-summaries:
	@echo "--> Deleting summarized markdown pages..."
ifeq ($(OS),Windows_NT)
	-$(RM_RF) $(subst /,\,$(SUMMARIZED_PAGES_DIR))
else
	-$(RM_RF) $(SUMMARIZED_PAGES_DIR)
endif

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