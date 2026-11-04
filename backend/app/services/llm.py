"""Client LLM DeepSeek via le SDK officiel OpenAI (base_url redirigée).

Le SDK `openai` gère déjà les retries sur erreurs transitoires
(timeout, connexion, 429) via `max_retries`. On convertit ensuite chaque
famille d'erreur en exception métier typée (voir `app.errors`).
"""
from __future__ import annotations

import json
import logging
import re

import openai
from openai import AsyncOpenAI

from app.config import Settings
from app.errors import (
    LlmAuthError,
    LlmError,
    LlmOutputError,
    LlmRateLimitError,
    LlmTimeoutError,
)

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.deepseek_api_key:
            raise LlmAuthError("Clé API LLM manquante : définissez DEEPSEEK_API_KEY.")
        self.settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        """Appelle le LLM et renvoie sa sortie déjà parsée en `dict` JSON."""
        kwargs: dict = {
            "model": self.settings.deepseek_model,
            "messages": messages,
            "temperature": self.settings.deepseek_temperature,
        }

        # deepseek-reasoner ne supporte PAS response_format / temperature / top_p.
        # Le JSON strict exige donc deepseek-chat (valeur par défaut).
        if self.settings.deepseek_model != "deepseek-reasoner":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except openai.AuthenticationError as exc:
            raise LlmAuthError("Authentification API refusée (clé invalide).") from exc
        except openai.RateLimitError as exc:
            raise LlmRateLimitError(
                "Quota API dépassé ou limite de débit atteinte."
            ) from exc
        except openai.APITimeoutError as exc:
            raise LlmTimeoutError(
                f"L'API n'a pas répondu dans les délais "
                f"({self.settings.llm_timeout_seconds}s)."
            ) from exc
        except openai.APIConnectionError as exc:
            raise LlmError("Erreur réseau lors de l'appel à l'API LLM.") from exc
        except openai.APIStatusError as exc:
            raise LlmError(
                f"L'API a renvoyé une erreur HTTP {exc.status_code} : {exc.message}"
            ) from exc
        except openai.OpenAIError as exc:  # filet de sécurité
            raise LlmError(f"Erreur inattendue de l'API LLM : {exc}") from exc

        content = response.choices[0].message.content or ""
        return self._parse_json(content)

    @staticmethod
    def _parse_json(content: str) -> dict:
        """Extrait et valide le JSON, même entouré de fences markdown."""
        text = content.strip()

        fence = _JSON_FENCE_RE.search(text)
        if fence:
            text = fence.group(1).strip()
        else:
            # Parfois le modèle renvoie du texte avant/après le JSON pur.
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LlmOutputError(
                f"Le modèle n'a pas renvoyé de JSON valide : {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise LlmOutputError("La sortie JSON doit être un objet.")

        return data
