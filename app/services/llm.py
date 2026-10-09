import json

import httpx
from pydantic import BaseModel, ValidationError

from app.config.settings import Settings


class LLMError(RuntimeError):
    pass


class LLMClient:
    """OpenAI-compatible chat-completions endpoint; base URL, key and model are configurable."""

    def __init__(self, settings: Settings):
        if not settings.llm_model:
            raise LLMError("LLM_MODEL is required")
        self.settings = settings
        self.last_usage: dict = {}

    def structured(self, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        url = self.settings.llm_api_base.rstrip("/") + "/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                json={
                    "model": self.settings.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system
                            + "\nReturn only valid JSON matching this schema: "
                            + json.dumps(schema.model_json_schema()),
                        },
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            self.last_usage = payload.get("usage", {})
            return schema.model_validate(json.loads(payload["choices"][0]["message"]["content"]))
        except (httpx.HTTPError, KeyError, ValueError, ValidationError) as exc:
            raise LLMError(f"LLM request or structured output failed: {exc}") from exc
