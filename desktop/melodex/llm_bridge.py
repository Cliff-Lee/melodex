from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests

from . import __version__ as MELODEX_VERSION


SYSTEM_PROMPT = r"""You are the optional intelligence layer inside Melodex, a desktop music player.
Your job is to help the listener choose, understand, sequence, and control music. Be concise and musical.

You receive a JSON context snapshot containing things such as the current track, current queue, current page,
taste summary, recent listening, saved vibes, and whether Flow is active. Never claim a track is playable unless
it appears in the supplied context or you are asking Melodex to search/resolve it.

For requests that only need a conversational answer, return normal text.
For requests that should change Melodex, return ONE JSON object and nothing else:
{
  "reply": "brief user-facing confirmation",
  "actions": [
    {"type": "ACTION_NAME", "args": {}}
  ]
}

Supported actions:
- play_for_me: {"mode":"balanced|comfort|rediscover|explore", "minutes":15-180, "adventure":0.0-1.0}
- search: {"query":"text", "category":"everything|songs|albums|artists"}
- play_pause: {}
- next: {}
- previous: {}
- stay_here: {}
- save_moment: {"label":"optional note"}
- flow_queue: {}
- open_view: {"view":"home|discover|library|playlists|moments|history|queue|lyrics"}
- import_playlist: {
    "name":"playlist name",
    "description":"short description",
    "tracks":[{"artist":"artist", "title":"track title", "album":"optional", "year":2024, "reason":"optional"}]
  }

When asked to make a playlist, use import_playlist. Use real released tracks and preserve intended order.
Melodex will resolve the requested tracks against its catalogue after you return them.
Do not invent unsupported action names. Do not wrap action JSON in Markdown fences.
"""


@dataclass
class LLMSettings:
    provider: str = "openwebui"
    endpoint: str = "http://localhost:3000/api/chat/completions"
    model: str = ""
    api_key: str = ""
    temperature: float = 0.45


class LLMClient:
    """Small provider-neutral client for an optional Melodex assistant.

    Supported wire formats:
    - OpenAI-compatible chat completions (including Open WebUI)
    - Ollama native /api/chat

    No provider SDK is required; requests is already a Melodex dependency.
    """

    def __init__(self, timeout: float = 75.0):
        self.timeout = float(timeout)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": f"Melodex/{MELODEX_VERSION}"})

    @staticmethod
    def default_endpoint(provider: str) -> str:
        provider = str(provider or "").strip().lower()
        if provider == "ollama":
            return "http://localhost:11434/api/chat"
        if provider == "openwebui":
            return "http://localhost:3000/api/chat/completions"
        if provider == "openai":
            return "https://api.openai.com/v1/responses"
        return "http://localhost:8000/v1/chat/completions"

    @staticmethod
    def _responses_text(data: Any) -> str:
        if not isinstance(data, dict):
            raise RuntimeError("OpenAI Responses API returned an unexpected response")
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        parts: list[str] = []
        for item in list(data.get("output") or []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for block in list(item.get("content") or []):
                if isinstance(block, dict) and block.get("type") in {"output_text", "text"} and isinstance(block.get("text"), str):
                    parts.append(str(block["text"]))
        if parts:
            return "\n".join(parts).strip()
        raise RuntimeError("OpenAI Responses API did not return assistant text")

    @staticmethod
    def _openai_text(data: Any) -> str:
        if not isinstance(data, dict):
            raise RuntimeError("LLM returned an unexpected response")
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0] if isinstance(choices[0], dict) else {}
            message = choice.get("message") if isinstance(choice, dict) else {}
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
                # Some OpenAI-compatible servers return content blocks.
                if isinstance(content, list):
                    parts: list[str] = []
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            parts.append(part["text"])
                    if parts:
                        return "\n".join(parts).strip()
            text = choice.get("text") if isinstance(choice, dict) else None
            if isinstance(text, str):
                return text.strip()
        # Be tolerant of simple proxy responses.
        for key in ("response", "content", "message"):
            value = data.get(key)
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, dict) and isinstance(value.get("content"), str):
                return str(value["content"]).strip()
        raise RuntimeError("LLM response did not contain assistant text")

    def complete(self, settings: LLMSettings, prompt: str, context: dict[str, Any] | None = None,
                 history: list[dict[str, str]] | None = None) -> str:
        provider = str(settings.provider or "openwebui").strip().lower()
        endpoint = str(settings.endpoint or self.default_endpoint(provider)).strip()
        model = str(settings.model or "").strip()
        if not endpoint:
            raise RuntimeError("No LLM endpoint is configured")
        if not model:
            raise RuntimeError("Choose an LLM model in Settings first")

        context_text = json.dumps(context or {}, ensure_ascii=False, separators=(",", ":"))
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "CURRENT MELODEX CONTEXT JSON:\n" + context_text},
        ]
        for message in list(history or [])[-10:]:
            role = str(message.get("role") or "").strip().lower()
            content = str(message.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": str(prompt or "").strip()})

        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"

        if endpoint.rstrip("/").endswith("/responses"):
            payload = {
                "model": model,
                "input": messages,
                "store": False,
            }
            response = self.session.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return self._responses_text(response.json())

        if provider == "ollama" or endpoint.rstrip("/").endswith("/api/chat"):
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": float(settings.temperature)},
            }
            response = self.session.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            message = data.get("message") if isinstance(data, dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return str(message["content"]).strip()
            if isinstance(data, dict) and isinstance(data.get("response"), str):
                return str(data["response"]).strip()
            raise RuntimeError("Ollama did not return assistant text")

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": float(settings.temperature),
        }
        response = self.session.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return self._openai_text(response.json())

    def test(self, settings: LLMSettings) -> str:
        return self.complete(settings, "Reply with exactly: Melodex connected", {"test": True}, [])

    def list_models(self, settings: LLMSettings, timeout: float = 8.0) -> list[str]:
        provider = str(settings.provider or "custom").strip().lower()
        endpoint = str(settings.endpoint or self.default_endpoint(provider)).strip()
        headers = {}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        candidates: list[str] = []
        if provider == "ollama" or endpoint.rstrip("/").endswith("/api/chat"):
            base = endpoint.rsplit("/api/chat", 1)[0]
            candidates = [base + "/api/tags"]
        elif endpoint.rstrip("/").endswith("/responses"):
            candidates = [endpoint.rstrip("/").rsplit("/responses", 1)[0] + "/models"]
        elif "/api/chat/completions" in endpoint:
            base = endpoint.split("/api/chat/completions", 1)[0]
            candidates = [base + "/api/models", base + "/v1/models"]
        elif endpoint.rstrip("/").endswith("/chat/completions"):
            candidates = [endpoint.rstrip("/").rsplit("/chat/completions", 1)[0] + "/models"]
        else:
            candidates = [endpoint.rstrip("/") + "/models"]

        last_error: Exception | None = None
        for url in candidates:
            try:
                response = self.session.get(url, headers=headers, timeout=float(timeout))
                response.raise_for_status()
                data = response.json()
                out: list[str] = []
                if isinstance(data, dict) and isinstance(data.get("models"), list):
                    for item in data["models"]:
                        if isinstance(item, dict):
                            name = item.get("name") or item.get("model") or item.get("id")
                        else:
                            name = item
                        if name:
                            out.append(str(name))
                if isinstance(data, dict) and isinstance(data.get("data"), list):
                    for item in data["data"]:
                        if isinstance(item, dict) and item.get("id"):
                            out.append(str(item["id"]))
                out = sorted(dict.fromkeys(x for x in out if x))
                if out:
                    return out
            except Exception as exc:
                last_error = exc
        if last_error:
            raise RuntimeError(str(last_error))
        return []

    @staticmethod
    def parse_action_response(text: str) -> tuple[str, list[dict[str, Any]]]:
        """Extract optional Melodex action JSON while remaining tolerant of normal prose."""
        raw = str(text or "").strip()
        if not raw:
            return "", []
        candidates = [raw]
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.I | re.S)
        if fence:
            candidates.insert(0, fence.group(1))
        # Also try the largest apparent object if the model added a sentence around it.
        first = raw.find("{")
        last = raw.rfind("}")
        if 0 <= first < last:
            candidates.append(raw[first:last + 1])
        for candidate in candidates:
            try:
                obj = json.loads(candidate)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            actions = obj.get("actions")
            if isinstance(actions, list):
                clean = [dict(x) for x in actions if isinstance(x, dict)]
                return str(obj.get("reply") or "Done.").strip(), clean
        return raw, []
