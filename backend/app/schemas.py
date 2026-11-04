"""Schémas de sortie de l'audit (validés en sortie du LLM).

Volontairement *tolérants* : chaque champ a une valeur par défaut
`Non mentionné dans le document` et les clés inconnues sont ignorées
(`extra="ignore"`). Ainsi, une réponse du LLM légèrement incomplète ne
fait pas planter la requête — seuls les types franchement erronés
déclenchent une relance (voir `AuditService.audit_text`).

⚠️ Sortie strictement factuelle (cf. CONCEPTION-AUDIT-PAYANT.md) : aucun champ
d'avis (`points_de_vigilance`, `resume`, `observations`). L'aiguillage
courrier/dossier est réalisé en aval, par règles déterministes — jamais ici.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

NON_MENTIONNE = "Non mentionné dans le document"


class Synthese(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type_contrat: str = NON_MENTIONNE
    assure: str = NON_MENTIONNE
    assureur: str = NON_MENTIONNE
    numero_contrat: str = NON_MENTIONNE
    activite_declaree: str = NON_MENTIONNE
    periode_validite: str = NON_MENTIONNE
    date_effet: str = NON_MENTIONNE


class Garantie(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nom: str = ""
    couverte: str = NON_MENTIONNE  # "Oui" | "Partielle" | "Non" | NON_MENTIONNE
    franchise: str = NON_MENTIONNE
    plafond: str = NON_MENTIONNE
    capital_indemnite: str = NON_MENTIONNE  # montant d'indemnisation
    exclusions: str = NON_MENTIONNE
    source: str = NON_MENTIONNE  # ex. "Page 12"


class PerteExploitation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    couverte: str = NON_MENTIONNE
    franchise: str = NON_MENTIONNE
    delai_carence: str = NON_MENTIONNE
    duree_max_indemnisation: str = NON_MENTIONNE
    indemnite_journaliere: str = NON_MENTIONNE
    source: str = NON_MENTIONNE


class ObligationsDelais(BaseModel):
    model_config = ConfigDict(extra="ignore")

    delai_declaration_sinistre: str = NON_MENTIONNE
    modalites_declaration: str = NON_MENTIONNE
    prescription: str = NON_MENTIONNE
    autres: str = NON_MENTIONNE


class MontantCle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intitule: str = ""
    montant: str = NON_MENTIONNE
    source: str = NON_MENTIONNE


class AuditResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    synthese: Synthese = Field(default_factory=Synthese)
    garanties: list[Garantie] = Field(default_factory=list)
    franchises_globales: str = NON_MENTIONNE
    exclusions_generales: list[str] = Field(default_factory=list)
    perte_exploitation: PerteExploitation = Field(default_factory=PerteExploitation)
    obligations_delais: ObligationsDelais = Field(default_factory=ObligationsDelais)
    montants_cles: list[MontantCle] = Field(default_factory=list)


class Orientation(BaseModel):
    """Aiguillage déterministe vers le courrier / la checklist (jamais le LLM).

    `courrier` = une valeur de `state.letterType` côté front ; `checklist` = une
    clé de `CHECKLISTS` (ex. `"emeute-pillage"`) ou `None` ; `raisons` = les
    faits factuels qui justifient l'aiguillage (jamais un jugement).
    """

    courrier: str = "declaration"
    checklist: str | None = None
    raisons: list[str] = Field(default_factory=list)


class AuditResponse(BaseModel):
    """Réponse complète de `/audit` : l'audit factuel + l'aiguillage en aval."""

    audit: AuditResult
    orientation: Orientation


class TextInput(BaseModel):
    """Corps de l'endpoint `/audit/text` (texte brut, pour tests sans PDF)."""

    text: str
