from __future__ import annotations

import json
from urllib import error, request

from railgpt_core.utils.config import RailGPTSettings


class OpenAICompatibleLLMClient:
    def __init__(self, settings: RailGPTSettings | None = None) -> None:
        self.settings = settings or RailGPTSettings.from_env()

    def _build_url(self) -> str:
        return f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        req = request.Request(
            self._build_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.llm_api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.settings.llm_timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"Unable to reach local LLM service at {self.settings.llm_base_url}: {exc.reason}"
            ) from exc

        try:
            return response_payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response payload: {response_payload}") from exc
