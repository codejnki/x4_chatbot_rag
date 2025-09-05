import json
from pathlib import Path

def load_text_file(file_path: str, description: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"{description} file not found at '{file_path}'")
    return path.read_text("utf-8")

def load_json_file(file_path: str, description: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"{description} file not found at '{file_path}'")
    return json.loads(path.read_text("utf-8"))
