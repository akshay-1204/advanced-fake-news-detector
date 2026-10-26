"""Loads prompt template files from backend/prompts/ and performs safe placeholder replacement.

CRITICAL: Uses plain string replacement (.replace) instead of str.format()
because prompts contain raw JSON blocks with curly braces which break str.format().
"""
import os
from typing import Dict, Any

PROMPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts"))


def load_prompt_template(filename: str) -> str:
    """Load the raw markdown prompt template from the backend/prompts directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file '{filename}' not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_prompt(template_name: str, variables: Dict[str, Any]) -> str:
    """Load a prompt and replace {{PLACEHOLDER}} with string values."""
    content = load_prompt_template(template_name)
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        str_val = "" if value is None else str(value)
        content = content.replace(placeholder, str_val)
    return content
