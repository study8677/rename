"""Namer that calls the Anthropic or OpenAI API directly (stdlib urllib only).

Fast and high quality. Requires an API key in the environment:
  - anthropic -> ANTHROPIC_API_KEY
  - openai    -> OPENAI_API_KEY
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .. import util
from .base import INSTRUCTION, Namer, build_excerpt

_TIMEOUT = 30

_DEFAULT_MODEL = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
}
_ENV_KEY = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class ApiNamer(Namer):
    def __init__(self, name: str, options: dict | None = None):
        self.name = name  # "anthropic" or "openai"
        self.options = options or {}
        self.model = str(self.options.get("model") or _DEFAULT_MODEL[name])

    def _api_key(self) -> str | None:
        key = self.options.get("api_key") or os.environ.get(_ENV_KEY[self.name])
        return key or None

    def available(self) -> bool:
        return self._api_key() is not None

    def _post(self, url: str, headers: dict, payload: dict) -> dict | None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:200]
            util.log(f"{self.name} API {exc.code}: {body}", level="debug")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            util.log(f"{self.name} API call failed: {exc}", level="debug")
        return None

    def generate(self, messages, *, old_title=None, cwd=None, tool=None):
        key = self._api_key()
        if not key:
            return None
        excerpt = build_excerpt(messages)
        if not excerpt:
            return None
        user_content = f"--- conversation ---\n{excerpt}\n--- end ---"

        if self.name == "anthropic":
            resp = self._post(
                "https://api.anthropic.com/v1/messages",
                {
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                {
                    "model": self.model,
                    "max_tokens": 32,
                    "system": INSTRUCTION,
                    "messages": [{"role": "user", "content": user_content}],
                },
            )
            if not resp:
                return None
            try:
                return resp["content"][0]["text"]
            except (KeyError, IndexError, TypeError):
                return None

        # openai
        resp = self._post(
            "https://api.openai.com/v1/chat/completions",
            {"authorization": f"Bearer {key}", "content-type": "application/json"},
            {
                "model": self.model,
                "max_tokens": 32,
                "messages": [
                    {"role": "system", "content": INSTRUCTION},
                    {"role": "user", "content": user_content},
                ],
            },
        )
        if not resp:
            return None
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None
