"""Pseudonymisation locale par expressions régulières (avant tout envoi externe).

⚠️ LIMITES CONNUES — à lire avant de considérer ce module comme « RGPD-compliant » :
- Il s'agit d'un *masquage par motifs*, PAS d'une anonymisation complète.
- Le nom de l'assuré / de l'entreprise, disséminé dans la prose sans motif
  régulier (« la Société s'engage… », « le Souscripteur déclare… »), n'est
  **pas** capturé par ces regex.
- Pour un usage sérieux : héberger un modèle en UE (voir README) et traiter
  l'intégralité du document comme une donnée personnelle (DPIA + consentement).

L'ordre d'application est maîtrisé : les motifs les plus spécifiques d'abord
(email → IBAN → téléphone → SIRET → SIREN → adresse → nom), ce qui évite qu'un
motif large ne « mange » un motif plus fin.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern

EMAIL_TOKEN = "[EMAIL_MASQUE]"
PHONE_TOKEN = "[TEL_MASQUE]"
SIRET_TOKEN = "[SIRET_MASQUE]"
SIREN_TOKEN = "[SIREN_MASQUE]"
IBAN_TOKEN = "[IBAN_MASQUE]"
ADDRESS_TOKEN = "[ADRESSE_MASQUE]"
NAME_TOKEN = "[NOM_MASQUE]"

# Email : forme usuelle (partie locale + domaine).
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")

# Téléphone FR fixe + mobile : 01..05 (fixe), 06..07 (mobile), séparateurs
# optionnels (espaces, points, tirets), indicatif +33 optionnel.
# Les lookarounds (?<!\d) / (?!\d) évitent de mordre dans un numéro plus long.
PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+33[\s.\-]?|0)"
    r"[1-9]"
    r"(?:[\s.\-]?\d{2}){4}"
    r"(?!\d)"
)

# SIRET : 14 chiffres, souvent écrits 3-3-3-5 (espaces/points optionnels).
SIRET_RE = re.compile(r"(?<![\dA-Za-z])\d{3}[\s.]?\d{3}[\s.]?\d{3}[\s.]?\d{5}(?!\d)")

# SIREN : 9 chiffres (3-3-3). Appliqué APRÈS le SIRET pour ne pas en capturer un morceau.
SIREN_RE = re.compile(r"(?<![\dA-Za-z])\d{3}[\s.]?\d{3}[\s.]?\d{3}(?!\d)")

# IBAN : 2 lettres (code pays) + 2 chiffres + 13 à 30 caractères alphanumériques.
# La longueur minimale limite les faux positifs sur des codes courts.
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[\s]?[A-Z0-9]){13,30}\b")

# Adresse : code postal français (5 chiffres) suivi d'un nom de ville capitalisé
# (accents et tirets pris en charge). Ex. "75001 Paris", "69000 Lyon".
POSTAL_CITY_RE = re.compile(
    r"\b\d{5}\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:\s[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+)*\b"
)

# Nom propre introduit par un titre ou une forme sociale.
# Heuristique : ne capture que les noms *précédés* d'un déclencheur explicite.
NAME_RE = re.compile(
    r"\b(?:Monsieur|Madame|Mademoiselle|M\.|Mme|Mlle|SARL|SAS|SASU|EURL|SA|SCI)\b"
    r"\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:\s[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+)*\b"
)


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: Pattern[str]
    token: str


RULES: list[Rule] = [
    Rule("email", EMAIL_RE, EMAIL_TOKEN),
    Rule("iban", IBAN_RE, IBAN_TOKEN),
    Rule("phone", PHONE_RE, PHONE_TOKEN),
    Rule("siret", SIRET_RE, SIRET_TOKEN),
    Rule("siren", SIREN_RE, SIREN_TOKEN),
    Rule("postal_city", POSTAL_CITY_RE, ADDRESS_TOKEN),
    Rule("name", NAME_RE, NAME_TOKEN),
]


class Anonymizer:
    """Applique les règles de masquage dans un ordre maîtrisé."""

    def anonymize(self, text: str) -> str:
        result = text
        for rule in RULES:
            result = rule.pattern.sub(rule.token, result)
        return result
