"""API Client helper module for Project Bite Streamlit Test UI."""

import json
import logging
from typing import Any, Dict, Generator, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

DEFAULT_API_BASE_URL = "http://localhost:8000"


class BiteAPIClient:
    def __init__(
        self, base_url: str = DEFAULT_API_BASE_URL, token: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> Dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def check_health(self) -> Tuple[bool, Dict[str, Any]]:
        """Check backend API liveness and readiness."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            if resp.status_code == 200:
                return True, resp.json()
            return False, {"error": f"Status code {resp.status_code}"}
        except Exception as e:
            return False, {"error": str(e)}

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user with email and password."""
        url = f"{self.base_url}/api/v1/auth/login"
        payload = {"email": email, "password": password}
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" in data:
            self.token = data["access_token"]
        return data

    def register(self, register_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new user account."""
        url = f"{self.base_url}/api/v1/auth/register"
        resp = requests.post(url, json=register_data, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" in data:
            self.token = data["access_token"]
        return data

    def generate_dev_token(
        self, email: Optional[str] = None, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Request a development JWT Bearer token."""
        url = f"{self.base_url}/api/v1/auth/dev-token"
        payload = {}
        if email:
            payload["email"] = email
        if user_id:
            payload["user_id"] = user_id

        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" in data:
            self.token = data["access_token"]
        return data

    def get_daily_dashboard(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetch daily dashboard metrics and meal log timeline."""
        url = f"{self.base_url}/api/v1/dashboard/daily"
        params = {}
        if target_date:
            params["target_date"] = target_date

        resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def analyze_meal(
        self,
        image_bytes: Optional[bytes] = None,
        image_url: Optional[str] = None,
        user_caption: Optional[str] = None,
        meal_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze meal image via Vision model & USDA resolver (auto-detects meal category if omitted)."""
        url = f"{self.base_url}/api/v1/meals/analyze"
        headers = self._headers()

        if image_bytes:
            files = {"file": ("meal_photo.jpg", image_bytes, "image/jpeg")}
            data = {}
            if meal_type:
                data["meal_type"] = meal_type
            if user_caption:
                data["user_caption"] = user_caption
            resp = requests.post(
                url, headers=headers, files=files, data=data, timeout=60
            )
        elif image_url:
            payload = {
                "image_url": image_url,
                "user_caption": user_caption,
            }
            if meal_type:
                payload["meal_type"] = meal_type
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
        else:
            raise ValueError("Either image_bytes or image_url must be provided.")

        resp.raise_for_status()
        return resp.json()

    def confirm_meal(
        self,
        items: list,
        meal_type: Optional[str] = None,
        user_caption: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist reviewed meal to database (upload time and meal category handled by backend)."""
        url = f"{self.base_url}/api/v1/meals/confirm"
        payload = {
            "user_caption": user_caption,
            "image_url": image_url,
            "items": items,
        }
        if meal_type:
            payload["meal_type"] = meal_type
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_profile(self) -> Dict[str, Any]:
        """Fetch current user profile and macro targets."""
        url = f"{self.base_url}/api/v1/profile"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_historical_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Fetch past days analytics breakdown including meal counts, target completions, and macro totals."""
        url = f"{self.base_url}/api/v1/dashboard/history?days={days}"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def update_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update current user profile and targets."""
        url = f"{self.base_url}/api/v1/profile"
        resp = requests.put(url, headers=self._headers(), json=profile_data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def stream_chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        client_timezone: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream chat assistant responses via Server-Sent Events (SSE)."""
        from datetime import datetime

        if not client_timezone:
            try:
                client_timezone = str(datetime.now().astimezone().tzinfo)
            except Exception:
                client_timezone = "UTC"

        url = f"{self.base_url}/api/v1/chat"
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "client_timezone": client_timezone,
        }

        headers = self._headers()
        headers["Accept"] = "text/event-stream"

        with requests.post(
            url, headers=headers, json=payload, stream=True, timeout=120
        ) as resp:
            resp.raise_for_status()
            current_event = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_str = line[len("data:") :].strip()
                    try:
                        data_json = json.loads(data_str)
                        evt = current_event
                        if isinstance(data_json, dict) and "event_type" in data_json:
                            evt = data_json["event_type"]
                        yield {"event": evt or "message", "data": data_json}
                    except json.JSONDecodeError:
                        yield {"event": current_event or "message", "data": data_str}
                    current_event = None

    def list_chat_sessions(self) -> list:
        """Fetch all previous chat sessions for authenticated user."""
        url = f"{self.base_url}/api/v1/chat/sessions"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def create_chat_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat conversation session."""
        url = f"{self.base_url}/api/v1/chat/sessions"
        payload = {}
        if title:
            payload["title"] = title
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_session_messages(self, session_id: str) -> list:
        """Retrieve chronological message history for a specific chat session."""
        url = f"{self.base_url}/api/v1/chat/sessions/{session_id}/messages"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def delete_chat_session(self, session_id: str) -> Dict[str, Any]:
        """Delete a chat session and all its messages."""
        url = f"{self.base_url}/api/v1/chat/sessions/{session_id}"
        resp = requests.delete(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
