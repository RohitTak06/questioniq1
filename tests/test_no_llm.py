"""Hard rule: no LLM or hosted AI libraries are imported in src/ or app/."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

BANNED = {
    "anthropic",
    "cohere",
    "google.genai",
    "google.generativeai",
    "huggingface_hub",
    "langchain",
    "litellm",
    "llama_cpp",
    "mistralai",
    "ollama",
    "openai",
    "sentence_transformers",
    "tiktoken",
    "transformers",
}


def is_banned(module: str) -> bool:
    """Return True if a dotted module name is, or sits inside, a banned package."""
    parts = module.split(".")
    return any(".".join(parts[: i + 1]) in BANNED for i in range(len(parts))) or (
        parts[0].startswith("langchain_")
    )


def banned_imports(source: str) -> list[str]:
    """Return the banned modules imported by a piece of Python source code."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names if is_banned(alias.name)]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [f"{node.module}.{alias.name}" for alias in node.names]
            found += [name for name in names if is_banned(name)]
    return found


@pytest.mark.parametrize(
    "source",
    [
        "import openai",
        "from anthropic import Anthropic",
        "import google.generativeai as genai",
        "from google import genai",
        "from transformers import pipeline",
        "from langchain_openai import ChatOpenAI",
    ],
)
def test_checker_catches_banned_imports(source: str) -> None:
    assert banned_imports(source)


def test_checker_allows_project_libraries() -> None:
    assert not banned_imports("import shap\nfrom sklearn.decomposition import NMF")


def test_src_and_app_have_no_banned_imports() -> None:
    files = [*ROOT.glob("src/**/*.py"), *ROOT.glob("app/**/*.py")]
    assert files
    for path in files:
        assert not banned_imports(path.read_text(encoding="utf-8")), path
