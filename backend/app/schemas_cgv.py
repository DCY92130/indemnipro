"""Schémas de sortie de la lecture de CGV (conditions générales de vente).

Même philosophie que l'audit assurance (`schemas.py`) : strictement factuel,
chaque champ a un défaut « Non mentionné dans le document », les clés inconnues
sont ignorées (`extra="ignore"`). Aucun champ d'avis — l'orientation vers la
checklist de négociation est calculée en aval par règles déterministes
(`orientation_cgv.py`), jamais ici.

Les CGV d'un fournisseur sont un document B2B public : pas de données de
particuliers, donc un champ d'application RGPD bien plus réduit que le contrat
d'assurance (le SIREN/raison sociale d'un fournisseur dans *ses propres* CGV ne
relèvent pas de la donnée personnelle).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

NON_MENTIONNE = "Non mentionné dans le document"


class SyntheseCgv(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fournisseur: str = NON_MENTIONNE
    titre_document: str = NON_MENTIONNE
    date_version: str = NON_MENTIONNE
    champ_application: str = NON_MENTIONNE  # à qui s'appliquent ces CGV


class ClauseCgv(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nom: str = ""  # ex. "Pénalités de retard"
    contenu: str = NON_MENTIONNE  # ce que dit la clause, fidèlement
    montant: str = NON_MENTIONNE  # chiffre/seuil clé de la clause, si présent
    source: str = NON_MENTIONNE  # ex. "Page 3"


class SeuilCgv(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intitule: str = ""
    valeur: str = NON_MENTIONNE
    source: str = NON_MENTIONNE


class CgvResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    synthese: SyntheseCgv = Field(default_factory=SyntheseCgv)
    clauses: list[ClauseCgv] = Field(default_factory=list)
    seuils: list[SeuilCgv] = Field(default_factory=list)


class CgvOrientation(BaseModel):
    """Checklist de négociation déterministe (jamais le LLM).

    `points_negociation` = les clauses dures détectées, formulées comme des
    faits à vérifier avant de signer (jamais un jugement sur leur caractère
    abusif). `raisons` = les faits factuels qui les justifient.
    """

    points_negociation: list[str] = Field(default_factory=list)
    raisons: list[str] = Field(default_factory=list)


class CgvResponse(BaseModel):
    """Réponse complète de `/audit/cgv` : la lecture factuelle + la checklist."""

    resultat: CgvResult
    orientation: CgvOrientation
