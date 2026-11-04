"""Extraction de texte depuis un PDF de contrat (PyMuPDF / fitz).

Chaque page est préfixée d'un marqueur `--- Page N ---`, ce qui permet au LLM
de citer ses sources (champ `source` des garanties).
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.errors import (
    PdfCorruptedError,
    PdfEncryptedError,
    PdfNoTextLayerError,
    PdfNotFoundError,
)

PAGE_MARKER = "--- Page {n} ---"


class PdfExtractor:
    """Extrait le texte brut d'un PDF, page par page, avec marqueurs de page."""

    def extract(self, path: str | Path) -> str:
        p = Path(path)
        if not p.exists():
            raise PdfNotFoundError(f"Fichier introuvable : {p}")

        doc: fitz.Document | None = None
        try:
            try:
                doc = fitz.open(str(p))
            except Exception as exc:  # noqa: BLE001 — PyMuPDF lève des types variés
                raise PdfCorruptedError(
                    f"Impossible d'ouvrir le PDF (fichier corrompu ou non-PDF) : {exc}"
                ) from exc

            if doc.needs_pass:
                raise PdfEncryptedError(
                    "Le PDF est protégé par mot de passe : fournissez une version déverrouillée."
                )
            if not doc.is_pdf:
                raise PdfCorruptedError("Le fichier n'est pas un PDF valide.")
            if doc.page_count == 0:
                raise PdfCorruptedError("Le PDF ne contient aucune page.")

            parts: list[str] = []
            has_text = False
            for index, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    has_text = True
                parts.append(f"{PAGE_MARKER.format(n=index)}\n{text}")

            # Un PDF "scanné" n'a pas de couche texte → rien à extraire.
            if not has_text:
                raise PdfNoTextLayerError(
                    "Aucun texte détecté : PDF probablement scanné (OCR requis)."
                )

            return "\n\n".join(parts).strip()
        finally:
            if doc is not None:
                doc.close()
