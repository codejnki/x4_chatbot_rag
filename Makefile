# Makefile for both Windows and Unix-like systems

# Data files
ZIP_FILE := x4-foundations-wiki.zip
WIKI_DIR := x4-foundations-wiki
PAGES_DIR := $(WIKI_DIR)/pages

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
    # Assumes '7z.exe' is in your system PATH.
    # You can install it with 'winget install -e --id 7zip.7zip'
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

# Unzip the wiki data.
data: $(PAGES_DIR)
$(PAGES_DIR): $(ZIP_FILE)
	@echo "--> Unzipping wiki data from $(ZIP_FILE)..."
	$(UNZIP_CMD)
	@echo "--> Wiki data is ready."

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
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "--> Cleanup complete."

# Help
help:
	@echo "Available targets:"
	@echo "  install - (Default) Creates venv and installs dependencies from requirements.txt."
	@echo "  data    - Unzips the wiki data from $(ZIP_FILE)."
	@echo "  venv    - Creates the virtual environment."
	@echo "  freeze  - Freezes the current environment's packages into requirements.txt."
	@echo "  clean   - Removes the virtual environment, wiki data, and Python cache files."
	@echo "  help    - Shows this help message."