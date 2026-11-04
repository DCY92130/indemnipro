"""Orchestration de la lecture de CGV : PDF → anonymisation → LLM → validation.

Miroir de `audit.py` (module assurance) : on réutilise exactement les mêmes
briques génériques (`PdfExtractor`, `PresidioAnonymizer`, `DeepSeekClient`) et
on ne change que ce qui est propre au domaine — le prompt (`prompt_cgv.py`) et
le schéma de sortie (`schemas_cgv.py`). L'aiguillage est appliqué par l'appelant
(`orienter_cgv`), jamais ici.
"""
from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings
from app.errors import LlmOutputError
from app.schemas_cgv import CgvResult
from app.services.llm import DeepSeekClient
from app.services.pdf import PdfExtractor
from app.services.presidio_anonymizer import PresidioAnonymizer
from app.services.prompt_cgv import build_cgv_messages

logger = logging.getLogger(__name__)

_RETRY_MESSAGE = (
    "Ta réponse précédente n'était pas un JSON valide conforme au schéma. "
    "Renvoie UNIQUEMENT le JSON demandé, sans texte autour."
)


class CgvService:
    """Extrait et structure les CGV d'un fournisseur (relevé factuel)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.extractor = PdfExtractor()
        self.anonymizer = PresidioAnonymizer(spacy_model=settings.spacy_model)
        self.llm = DeepSeekClient(settings)

    async def audit_file(self, path: str | Path) -> CgvResult:
        raw_text = self.extractor.extract(path)
        return await self.audit_text(raw_text)

    async def audit_text(self, raw_text: str) -> CgvResult:
        anonymized = self._enforce_budget(self.anonymizer.anonymize(raw_text))
        messages = build_cgv_messages(anonymized)
        logger.info(
            "Appel LLM (CGV) — %d caractères vers %s",
            len(anonymized),
            self.settings.deepseek_model,
        )

        last_exc: Exception | None = None
        for attempt in range(self.settings.llm_output_retries + 1):
            try:
                data = await self.llm.complete_json(messages)
                return CgvResult.model_validate(data)
            except (LlmOutputError, ValidationError) as exc:
                last_exc = exc
                if attempt >= self.settings.llm_output_retries:
                    break
                messages.append({"role": "user", "content": _RETRY_MESSAGE})

        raise LlmOutputError(
            "Le modèle n'a pas produit un JSON conforme au schéma après relance."
        ) from last_exc

    def _enforce_budget(self, text: str) -> str:
        """Tronque à une frontière de page si le texte dépasse la limite."""
        if len(text) <= self.settings.max_input_chars:
            return text
        logger.warning(
            "Texte tronqué : %d > %d caractères.", len(text), self.settings.max_input_chars
        )
        cut = text.rfind("\n\n--- Page", 0, self.settings.max_input_chars)
        return text[:cut] if cut != -1 else text[: self.settings.max_input_chars]
