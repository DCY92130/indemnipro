"""Aiguillage CGV → checklist de négociation (déterministe, jamais le LLM).

Même principe que `orientation.py` pour l'assurance : on ne demande pas au
modèle d'émettre un avis, on applique des règles déterministes sur les champs
factuels de la lecture. Ici, on transforme les clauses « dures » détectées en
points à vérifier avant de signer — formulés comme des faits, jamais comme un
jugement sur leur caractère abusif.

Le commerçant qui lit les CGV d'un fournisseur ne reçoit pas un courrier de
sinistre : il reçoit une liste de points à négocier/vérifier. D'où le retour
`{ points_negociation, raisons }` plutôt que `{ courrier, checklist }`.
"""
from __future__ import annotations

import unicodedata

from app.schemas_cgv import CgvResult, NON_MENTIONNE

# (mot-clé sans accent, libellé humain) — ordre important : on teste dans
# l'ordre et on s'arrête à la première correspondance pour éviter de dupliquer
# un point. Le matching est accent-insensible (`_normalize`), d'où des mots-clés
# volontairement écrits sans accent.
CLAUSES_DURES: tuple[tuple[str, str], ...] = (
    ("penalite", "Pénalités de retard de paiement"),
    ("exclusiv", "Clause d'exclusivité"),
    ("reconduction", "Reconduction tacite du contrat"),
    ("resiliation", "Résiliation / préavis"),
    ("minimum", "Minimum de commande / de facturation"),
    ("revision", "Révision de prix"),
    ("prix", "Conditions de prix"),
    ("reserve de propriete", "Réserve de propriété"),
    ("tribunal", "Juridiction / tribunal compétent"),
    ("loi applicable", "Loi applicable"),
    ("responsabilite", "Limitation de responsabilité"),
    ("garantie", "Garanties (vices cachés, conformité)"),
)


def _normalize(text: str) -> str:
    """Minuscules + sans accents, pour un matching robuste aux variantes du LLM."""
    text = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _clause_dure(clause) -> str | None:
    """Renvoie le libellé humain si la clause correspond à une clause dure."""
    nom = _normalize(clause.nom or "")
    contenu = _normalize(clause.contenu or "")
    for mot_cle, libelle in CLAUSES_DURES:
        if mot_cle in nom or mot_cle in contenu:
            return libelle
    return None


def orienter_cgv(resultat: CgvResult) -> dict[str, list[str]]:
    """Transforme la lecture factuelle en checklist de négociation.

    Chaque clause dure détectée devient un point à vérifier, rédigé comme un
    fait (libellé + ce que dit le document + source) — sans qualificatif.
    """
    points: list[str] = []
    raisons: list[str] = []

    for clause in resultat.clauses:
        contenu = (clause.contenu or "").strip()
        if contenu == "" or contenu.lower() == NON_MENTIONNE.lower():
            continue
        libelle = _clause_dure(clause)
        if libelle is None:
            continue

        source = (clause.source or "").strip()
        origine = f"source : {source}" if source else "source non citée"
        points.append(f"{libelle} — {contenu} ({origine}).")
        raisons.append(f"Clause « {clause.nom or libelle} » détectée dans le document.")

    return {"points_negociation": points, "raisons": raisons}
