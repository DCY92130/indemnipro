"""Orientation déterministe vers le courrier / la checklist qui conviennent.

L'aiguillage ne passe **pas** par le LLM (risque d'avis + d'hallucination) :
des règles lisibles sur les champs factuels de l'audit suffisent. Chaque
résultat est exprimé par un fait (« la garantie X est absente (Page N) »),
jamais par un jugement — cf. CONCEPTION-AUDIT-PAYANT.md §6.
"""
from __future__ import annotations

from app.schemas import AuditResult

# Courriers admissibles côté front (state.letterType).
COURRIER_DEFAUT = "declaration"
COURRIER_CONTESTATION = "contestation"

# Valeurs de « couverte » qui signifient que la garantie n'est pas effective.
NON_COUVERT = {"non", "non mentionné dans le document"}

# Mots-clés signalant une exclusion / restriction « émeutes ».
MOTS_EMEUTE = ("émeute", "attroupement", "mouvement populaire", "mouvements populaires")

# Marqueurs d'un délai de déclaration raccourci (vol : 2 jours).
DELAI_RACCOURCI = ("2 jour", "deux jour", "48 h", "48h", "48 heures")


def _norm(texte: str | None) -> str:
    return (texte or "").strip().lower()


def _contient_emeute(texte: str | None) -> bool:
    t = _norm(texte)
    return any(mot in t for mot in MOTS_EMEUTE)


def orienter(audit: AuditResult) -> dict:
    """Retourne `{ courrier, checklist, raisons }` à partir d'un audit factuel.

    `courrier` vaut une des valeurs de `state.letterType` (défaut `declaration`,
    escalade `contestation`) ; `checklist` vaut une clé de `CHECKLISTS` ou
    `None` ; `raisons` liste les faits factuels qui justifient l'aiguillage.
    """
    raisons: list[str] = []
    courrier = COURRIER_DEFAUT
    checklist: str | None = None

    # 1. Perte d'exploitation absente ou non mentionnée.
    if audit.perte_exploitation.couverte.strip().lower() in NON_COUVERT:
        courrier = COURRIER_CONTESTATION
        raisons.append(
            "La garantie perte d'exploitation est absente ou non mentionnée dans le document."
        )

    # 2. Exclusion / restriction « émeutes, attroupement, mouvement populaire ».
    emeute_trouvee = any(_contient_emeute(excl) for excl in audit.exclusions_generales)
    if not emeute_trouvee:
        emeute_trouvee = any(
            _contient_emeute(g.nom) or _contient_emeute(g.exclusions)
            for g in audit.garanties
        )
    if emeute_trouvee:
        courrier = COURRIER_CONTESTATION
        checklist = "emeute-pillage"
        raisons.append(
            "Une exclusion ou restriction liée aux émeutes, attroupements ou "
            "mouvements populaires figure au contrat."
        )

    # 3. Garantie vol non couverte.
    for g in audit.garanties:
        if "vol" in _norm(g.nom) and g.couverte.strip().lower() in NON_COUVERT:
            courrier = COURRIER_CONTESTATION
            source = g.source or "le document"
            raisons.append(f"La garantie vol est absente ou non mentionnée ({source}).")
            break

    # 4. Délai de déclaration raccourci → rappel factuel (reste « declaration »).
    delai = _norm(audit.obligations_delais.delai_declaration_sinistre)
    if any(mot in delai for mot in DELAI_RACCOURCI):
        raisons.append(
            "Le délai de déclaration indiqué est raccourci : "
            f"{audit.obligations_delais.delai_declaration_sinistre}."
        )

    return {
        "courrier": courrier,
        "checklist": checklist,
        "raisons": raisons,
    }
