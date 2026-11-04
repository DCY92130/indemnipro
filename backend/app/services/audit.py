"""Orchestration du pipeline : extraction → anonymisation → LLM → validation."""
from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings
from app.errors import LlmOutputError
from app.schemas import AuditResult
from app.services.llm import DeepSeekClient
from app.services.presidio_anonymizer import PresidioAnonymizer
from app.services.pdf import PdfExtractor
from app.services.prompt import build_messages

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.extractor = PdfExtractor()
        self.anonymizer = PresidioAnonymizer(spacy_model=settings.spacy_model)
        self.llm = DeepSeekClient(settings)

    async def audit_file(self, path: str | Path) -> AuditResult:
        """Audite un PDF de contrat : extraction, anonymisation, LLM, validation."""
        raw_text = self.extractor.extract(path)
        return await self.audit_text(raw_text)

    async def audit_text(self, raw_text: str) -> AuditResult:
        """Audite un texte déjà extrait (utile aussi pour tester sans PDF)."""
        anonymized = self._enforce_budget(self.anonymizer.anonymize(raw_text))

        messages = build_messages(anonymized)
        logger.info(
            "Appel LLM — %d caractères (anonymisés) vers %s",
            len(anonymized),
            self.settings.deepseek_model,
        )

        last_exc: Exception | None = None
        for attempt in range(self.settings.llm_output_retries + 1):
            try:
                data = await self.llm.complete_json(messages)
                return AuditResult.model_validate(data)
            except (LlmOutputError, ValidationError) as exc:
                last_exc = exc
                if attempt >= self.settings.llm_output_retries:
                    break
                # Relance : on demande explicitement une sortie JSON conforme.
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Ta réponse précédente n'était pas un JSON valide conforme "
                            "au schéma. Renvoie UNIQUEMENT le JSON demandé, sans texte "
                            "autour, avec les bonnes clés et les bons types."
                        ),
                    }
                )

        raise LlmOutputError(
            "Le modèle n'a pas produit un JSON conforme au schéma après relance."
        ) from last_exc

    def _enforce_budget(self, text: str) -> str:
        """Tronque le texte au-delà de la limite, à une frontière de page propre."""
        if len(text) <= self.settings.max_input_chars:
            return text

        logger.warning(
            "Texte tronqué : %d > %d caractères (risque de perte d'information). "
            "Envisagez un découpage par lots pour les très longs contrats.",
            len(text),
            self.settings.max_input_chars,
        )
        cut = text.rfind("\n\n--- Page", 0, self.settings.max_input_chars)
        return text[:cut] if cut != -1 else text[: self.settings.max_input_chars]
