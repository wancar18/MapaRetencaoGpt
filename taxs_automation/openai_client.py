"""Cliente OpenAI com retentativas e prompts estruturados."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import openai

from .config import OPENAI_MODEL_DEFAULT


def _init_client() -> openai.OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "A variável de ambiente OPENAI_API_KEY precisa estar configurada para usar a API."
        )
    return openai.OpenAI(api_key=api_key)


@dataclass
class OpenAIResponse:
    content: str
    raw: Dict[str, Any]


class OpenAIHelper:
    """Wrapper simples para chamadas ao endpoint de chat completions."""

    def __init__(self, model: Optional[str] = None, max_attempts: int = 3, timeout_s: float = 30.0) -> None:
        self._client = _init_client()
        self.model = model or os.getenv("OPENAI_MODEL", OPENAI_MODEL_DEFAULT)
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s

    def chat_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> OpenAIResponse:
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    timeout=self.timeout_s,
                )
                content = resp.choices[0].message.content or ""
                return OpenAIResponse(content=content.strip(), raw=resp.model_dump())
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                wait = min(2.0 * attempt, 6.0)
                print(f"[OpenAIHelper] Tentativa {attempt} falhou: {exc}. Nova tentativa em {wait:.1f}s")
                time.sleep(wait)
        raise RuntimeError(f"Falha ao consultar OpenAI após {self.max_attempts} tentativas: {last_err}")


__all__ = ["OpenAIHelper", "OpenAIResponse"]
