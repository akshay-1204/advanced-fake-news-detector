"""Provider-agnostic LLM client for Satyavani AI.

Supports:
- Ollama (default local development)
- Google Gemini (via REST API)
- Groq (via OpenAI-compatible REST API)
Enforces temperature 0.0 - 0.2, requests JSON mode, includes 1 retry,
and provides mock hooks for deterministic offline testing.
"""
import json
import logging
import re
from typing import Optional, Dict, Any, Callable
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Testing hook
_MOCK_LLM_HANDLER: Optional[Callable[[str, bool], str]] = None


def set_mock_llm_handler(handler: Optional[Callable[[str, bool], str]]) -> None:
    """Set a mock handler for testing to completely isolate from network/LLM servers."""
    global _MOCK_LLM_HANDLER
    _MOCK_LLM_HANDLER = handler


def clean_json_text(text: str) -> str:
    """Strip markdown code fences and extract valid JSON substring."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # If extra text precedes or follows JSON, slice between first { and last }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace:last_brace + 1]

    # Or between [ and ] for arrays
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return cleaned[first_bracket:last_bracket + 1]

    return cleaned


def _call_ollama(prompt: str, json_mode: bool, timeout: float = 30.0) -> str:
    """Send prompt to local Ollama instance."""
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload: Dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }
    if json_mode:
        payload["format"] = "json"

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


def _call_gemini(prompt: str, json_mode: bool, timeout: float = 20.0) -> str:
    """Send prompt to Google Gemini REST API."""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in .env.")

    model_name = settings.LLM_MODEL if "gemini" in settings.LLM_MODEL else "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    generation_config: Dict[str, Any] = {
        "temperature": 0.1,
    }
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config
    }

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""


def _call_groq(prompt: str, json_mode: bool, timeout: float = 20.0) -> str:
    """Send prompt to Groq API."""
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured in .env.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}

    payload: Dict[str, Any] = {
        "model": settings.LLM_MODEL if "llama" in settings.LLM_MODEL or "mixtral" in settings.LLM_MODEL else "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            return choices[0]["message"].get("content", "")
        return ""

# ---------------------------------------------------------------------
# NVIDIA NIM inference
# ---------------------------------------------------------------------
def _call_nvidia(prompt: str, json_mode: bool, timeout: float = 60.0) -> str:
    """Send prompt to NVIDIA hosted NIM endpoint.
    Uses the NVIDIA_BASE_URL from settings and the API key from NVIDIA_API_KEY.
    """
    api_key = settings.NVIDIA_API_KEY
    if not api_key:
        raise ValueError("NVIDIA_API_KEY is not configured in .env.")
    url = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload: Dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            return choices[0]["message"].get("content", "")
        return ""


def call_llm(prompt: str, json_mode: bool = True, max_retries: int = 1) -> str:
    """Execute LLM call across configured provider with 1 retry.

    Returns the cleaned raw response string.
    """
    if _MOCK_LLM_HANDLER is not None:
        return _MOCK_LLM_HANDLER(prompt, json_mode)

    provider = settings.LLM_PROVIDER.lower().strip()
    attempts = 0
    last_error = None

    while attempts <= max_retries:
        try:
            if provider == "ollama":
                res = _call_ollama(prompt, json_mode)
            elif provider == "gemini":
                res = _call_gemini(prompt, json_mode)
            elif provider == "groq":
                res = _call_groq(prompt, json_mode)
            elif provider == "nvidia":
                res = _call_nvidia(prompt, json_mode)
            else:
                raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Allowed: ollama | gemini | groq | nvidia")

            if json_mode:
                return clean_json_text(res)
            return res.strip()

        except Exception as exc:
            last_error = exc
            attempts += 1
            logger.warning("LLM call attempt %d failed for provider '%s': %s", attempts, provider, exc)

    logger.error("All LLM attempts exhausted. Last error: %s", last_error)
    raise RuntimeError(f"LLM request failed after {max_retries + 1} attempts: {last_error}")


def call_llm_json(prompt: str, schema_cls: Any) -> Optional[Any]:
    """Call LLM in JSON mode and validate with a Pydantic schema class.

    Retries once on JSON decoding/validation error.
    """
    for attempt in range(2):
        try:
            raw_text = call_llm(prompt, json_mode=True)
            cleaned = clean_json_text(raw_text)
            parsed_dict = json.loads(cleaned)
            return schema_cls.model_validate(parsed_dict)
        except Exception as exc:
            logger.warning("Attempt %d to parse LLM JSON into %s failed: %s", attempt + 1, schema_cls.__name__, exc)
    return None
