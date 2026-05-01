"""File-system tools for agents that read and inspect source code."""

from pathlib import Path

from langchain.tools import tool
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    path: str = Field(description="Absolute or relative path to the file to read")


class ListFilesInput(BaseModel):
    directory: str = Field(description="Directory to list files in")
    pattern: str = Field(default="*", description="Glob pattern to filter files, e.g. '*.py'")
    recursive: bool = Field(default=False, description="Whether to search recursively")


class SearchInFileInput(BaseModel):
    path: str = Field(description="File path to search in")
    keyword: str = Field(description="Keyword or substring to search for")


@tool(args_schema=ReadFileInput)
def read_file(path: str) -> str:
    """Read and return the full text content of a source file."""
    p = Path(path)
    if not p.exists():
        return f"ERROR: file not found — {path}"
    if not p.is_file():
        return f"ERROR: path is not a file — {path}"
    try:
        return p.read_text(encoding="utf-8")
    except Exception as exc:
        return f"ERROR: could not read file — {exc}"


@tool(args_schema=ListFilesInput)
def list_files(directory: str, pattern: str = "*", recursive: bool = False) -> str:
    """List files in a directory matching an optional glob pattern. Returns newline-separated paths."""
    d = Path(directory)
    if not d.exists():
        return f"ERROR: directory not found — {directory}"
    if not d.is_dir():
        return f"ERROR: path is not a directory — {directory}"

    glob_fn = d.rglob if recursive else d.glob
    matches = [str(p) for p in glob_fn(pattern) if p.is_file()]
    if not matches:
        return f"No files matching '{pattern}' in {directory}"
    return "\n".join(sorted(matches))


@tool(args_schema=SearchInFileInput)
def search_in_file(path: str, keyword: str) -> str:
    """Search for a keyword in a file and return matching lines with line numbers."""
    p = Path(path)
    if not p.exists():
        return f"ERROR: file not found — {path}"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return f"ERROR: could not read file — {exc}"

    hits = [
        f"  line {i + 1}: {line}"
        for i, line in enumerate(lines)
        if keyword.lower() in line.lower()
    ]
    if not hits:
        return f"'{keyword}' not found in {path}"
    return f"Found {len(hits)} match(es) for '{keyword}' in {path}:\n" + "\n".join(hits)
