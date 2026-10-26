"""Backend API client for Streamlit frontend with timeouts and graceful error handling."""
import logging
from typing import Dict, Any, Optional
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class SatyavaniAPIClient:
    """Handles communication between Streamlit UI and FastAPI backend."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.BACKEND_URL).rstrip("/")

    def get_health(self, timeout: float = 15.0) -> Dict[str, Any]:
        """Check backend health and connection status."""
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{self.base_url}/health")
                if resp.status_code == 200:
                    return {"connected": True, "data": resp.json()}
                return {"connected": False, "error": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    def send_chat(self, query: str, session_id: Optional[str] = None, timeout: float = 90.0) -> Dict[str, Any]:
        """Send chat query or claim to POST /chat endpoint."""
        url = f"{self.base_url}/chat"
        payload = {"query": query, "session_id": session_id}

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    return {"success": True, "data": resp.json()}
                elif resp.status_code == 429:
                    return {
                        "success": False,
                        "error_type": "rate_limit",
                        "error": "Rate limit exceeded. Please wait a moment before sending another message."
                    }
                else:
                    err_msg = resp.json().get("detail", f"Server returned error code {resp.status_code}")
                    return {"success": False, "error_type": "server_error", "error": err_msg}

        except httpx.ConnectError:
            return {
                "success": False,
                "error_type": "backend_down",
                "error": "Unable to connect to Satyavani backend. Please ensure the backend is running (`uvicorn backend.main:app --port 8000`)."
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "error_type": "timeout",
                "error": "Request timed out while waiting for verification. Please try again."
            }
        except Exception as exc:
            return {
                "success": False,
                "error_type": "unknown",
                "error": f"An unexpected error occurred: {str(exc)}"
            }
