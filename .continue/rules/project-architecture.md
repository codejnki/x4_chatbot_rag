# Project Architecture

- This is a Python program that builds a RAG engine
- It has two components a data pipeline that cleans and sanitizes data and the fast api that hosts it
 - src/00_unzip_data.py
 - src/01a_html-to_md.py
 - src/01b_summarize_md.py
 - src/01c_get_files_to_process.py
 - src/01d_process_changelogs.py
 - src/02_chunk_corpus.py
 - src/02b_merge_chunks.py
 - src/03_build_vector_store.py
 - src/04_generate_keywords.py
 - src/05_refine_keywords.py
- Application Pipeline Files
 - src/api_models.py
 - src/api_routes.py
 - src/config.py
 - src/files_utils.py
 - src/logging_config.py
 - src/main.py
 - src/rag_chain.py
 - src/researcher.py
 - src/retriever.py
- All prompts are in the root folder in a directory called prompts/

## Coding Standards
- Use Python for all new code files
- Follow Python best practices
- Follow the existing naming conventions
- Use Taskfile.yaml for all new tasks
