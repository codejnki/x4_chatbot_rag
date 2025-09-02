# Chatbot RAG Project

This project is a chatbot using the Retrieval-Augmented Generation (RAG) pattern.

## Development Environment Setup

This project uses a `Makefile` to automate the setup and management of the development environment. The setup process is designed to work seamlessly across Windows, macOS, and Linux.

### Prerequisites

Before you begin, ensure you have the following installed on your system:

1.  **Python 3.8+**
2.  **Make**: A build automation tool.
    *   **On Windows**: You can install `make` via a package manager like Chocolatey (`choco install make`) or by installing the build tools included with Git for Windows (which provides `make` in its Git Bash terminal).
    *   **On macOS**: `make` is included with the Xcode Command Line Tools. You can install them by running `xcode-select --install` in your terminal.
    *   **On Linux**: `make` is usually available in the `build-essential` package or equivalent. For example, on Debian/Ubuntu: `sudo apt-get install build-essential`.
3.  A download of the [X4 Community Wiki](https://wiki.egosoft.com:1337/X4%20Foundations%20Wiki/) in `html` format.  You can download a copy in a zip file directly from the main page.  Place it in this folder and name it `x4-foundations-wiki.zip`

### Installation

With the prerequisites installed, setting up the project is a single command. Open your terminal in the project's root directory and run:

```sh
make install
```

### Wiki Data

We first need to unpack our copy of the X4 community wiki.  Open the terminal in the project's root directory and run:

```sh
make data
```

### Corpus Data

Once we have the Wiki data downloaded, we need to turn it into a format that we can easily parse.  The `01_generate_corpus.py` script will pull each document from the wiki and convert it into a Markdown compatible string.  It will strip links and images from the text.  It will then put all the pages into a single `x4_wiki_corpus.json` file.

```sh
make corpus
```