# X4 Foundations RAG Chatbot

This project is a 100% local, Retrieval-Augmented Generation (RAG) chatbot that is an expert on the video game "X4 Foundations." It is designed to act as a conversational AI partner, providing both factual information and engaging, in-character dialogue.

## Core Architecture: The "Researcher/Actor" Model

Standard RAG architectures can struggle when retrieved documents are irrelevant or contain conflicting facts. To solve this, this project implements a sophisticated two-stage pipeline:

1.  **The "Researcher" (Fact-Finding Stage):** When a user's query contains a specific in-game keyword, the system first retrieves multiple relevant documents from a vector store. The Researcher model is then given a synthetic, factual task: "Summarize the key information about [keywords] from the provided text." Its sole job is to analyze the documents and synthesize a single, dense paragraph of verified, relevant facts. If no facts can be found, it signals a failure.

2.  **The "Actor" (Performance Stage):** This is the final, user-facing LLM. It receives the user's original, conversational query and, crucially, the clean, synthesized paragraph from the Researcher as its "context." This allows the Actor to focus entirely on creative, in-character performance, using the pre-vetted context as its ground truth.

This decoupling of fact-finding from performance is the key to providing responses that are both factually accurate and conversationally engaging.

## Development Environment Setup

This project uses a `Makefile` to automate the setup and management of the development environment. The setup process is designed to work seamlessly across Windows, macOS, and Linux.

### Prerequisites

Before you begin, ensure you have the following installed on your system:

1.  **Python 3.8+**
2.  **Make**: A build automation tool.
    * **On Windows**: You can install `make` via Chocolatey (`choco install make`) or by using the tools included with Git for Windows.
    * **On macOS**: `make` is included with the Xcode Command Line Tools (`xcode-select --install`).
    * **On Linux**: `make` is usually available in the `build-essential` package (`sudo apt-get install build-essential`).
3.  **7-Zip (Windows Only)**: To handle long file paths during data extraction, it is recommended to install 7-Zip and ensure it's in your system's PATH.
    `winget install -e --id 7zip.7zip`
4.  **LM Studio**: This project relies on a local LLM server. Download and install LM Studio from [https://lmstudio.ai/](https://lmstudio.ai/).
5.  **Required Models**:
    * **LLM for Keyword Generation & Chat**: Download `meta-llama-3-8b-instruct` within LM Studio. This model is used for both the intensive keyword generation step and the final chat responses. While other models may work, this is the one that has been validated.
    * **Embedding Model**: The `03_build_vector_store.py` script will automatically download the `sentence-transformers/all-MiniLM-L6-v2` model from Hugging Face the first time it is run.
6.  **X4 Community Wiki Data**: Download a copy of the wiki in `html` format from the main page of the [X4 Community Wiki](https://wiki.egosoft.com:1337/X4%20Foundations%20Wiki/). Place the downloaded zip file in the root of this project and name it `x4-foundations-wiki.zip`.

## Data Preparation and Execution

The entire data pipeline, from unzipping the wiki to running the final application, is managed by the `Makefile`.

### One-Step Execution

To build all necessary data artifacts and start the chatbot server, simply run the following command from your terminal (ensure you are **not** inside an active virtual environment):

`make`

This will automatically execute every step in the data pipeline in the correct order and then launch the FastAPI server.

### Data Preparation Pipeline (Step-by-Step)

The `make` command automates the following sequence. You can also run each step individually.

#### 1. Unzip Wiki Data
Unpacks the raw HTML files from the wiki download.

`make data`

#### 2. Generate Corpus
Parses all HTML files, cleans the text, converts it to Markdown, and consolidates everything into a single `x4_wiki_corpus.json` file.

`make corpus`

#### 3. Chunk The Corpus
Breaks the large documents in the corpus into smaller, overlapping chunks suitable for embedding and stores them in `x4_wiki_chunks.json`.

`make chunks`

#### 4. Build Vector Store
Creates a searchable vector database from the text chunks. This process uses the `sentence-transformers` model to generate embeddings and saves them to the `faiss_index` directory.

`make vector-store`

#### 5. Generate Keywords
This is the most time-intensive step. It uses the locally running LLM in LM Studio to read every chunk and extract a comprehensive list of in-game keywords, which is saved to `x4_keywords.json`. This process is parallelized and uses a cache (`.keyword_cache`) to allow it to be resumed if interrupted.

`make keywords`

#### 6. Refine Keywords
Applies a series of filters to the raw keyword list to remove common English words and other noise, resulting in a clean, domain-specific list in `x4_keywords_refined.json`.

`make keywords-refined`

### Starting the Server

Once all the data artifacts have been built, the `make` command will automatically start the FastAPI server, which provides an OpenAI-compatible API endpoint for the chatbot.