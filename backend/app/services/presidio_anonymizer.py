"""Anonymisation enrichie par Microsoft Presidio (NER), en complément des regex.

Pipeline à deux passes (cf. CONCEPTION-AUDIT-PAYANT.md §4) :

1. `Anonymizer` (regex) — masque les identifiants *structurés* (email, téléphone,
   SIRET/SIREN, IBAN, adresse, nom introduit par un titre). Déjà en place.
2. Presidio Analyzer (spaCy `fr_core_news_lg`) — détecte les entités *en prose*
   (PERSON, ORGANIZATION) qui échappent aux regex, puis Anonymizer les remplace
   par des jetons `[TYPE_MASQUE]`.

Le tout est auto-hébergé : aucune donnée ne quitte la machine. Si Presidio ou le
modèle spaCy est absent, la classe se replie silencieusement sur la passe regex
seule — le pipeline reste fonctionnel (voir `available`).
"""
from __future__ import annotations

import logging

from app.services.anonymizer import Anonymizer

logger = logging.getLogger(__name__)

# Entité Presidio → jeton de masquage (vocabulaire « [TYPE_MASQUE] » attendu par
# le prompt d'extraction).
#
# Volontairement SANS « LOCATION » : le modèle français spaCy classe à tort des
# termes du domaine assurance comme des lieux (« Capital » au sens de capitaux →
# LOCATION), ce qui corromprait les clauses à extraire (ex. « Capital mobilier »
# → « [LIEU_MASQUE] mobilier »). Les adresses structurées (« 69002 Lyon ») sont
# déjà masquées par la passe regex (règle `postal_city`) ; un nom de ville isolé
# est une donnée à faible pouvoir identifiant, qu'on accepte de laisser tel quel
# pour préserver la fidélité de l'extraction.
ENTITY_TOKEN = {
    "PERSON": "[NOM_MASQUE]",
    "NRP": "[NOM_MASQUE]",
    "ORGANIZATION": "[ORG_MASQUE]",
}

# Seules les entités *en prose* sont traitées ici : les identifiants structurés
# (email, tel, IBAN…) sont déjà couverts par la passe regex.
ENTITIES = list(ENTITY_TOKEN.keys())

SPACY_MODEL = "fr_core_news_lg"


class PresidioAnonymizer:
    """Anonymisation regex (structuré) + Presidio NER (prose), avec repli.

    `spacy_model` est configurable : `fr_core_news_lg` (571 Mo, qualité max) en
    local, `fr_core_news_md` (~45 Mo) recommandé pour un hébergement léger. Le
    repli regex reste actif si le modèle demandé est absent.
    """

    def __init__(self, spacy_model: str = SPACY_MODEL, enabled: bool = True) -> None:
        self._spacy_model = spacy_model
        self._enabled = enabled
        self._regex = Anonymizer()
        self._analyzer = None
        self._anonymizer_engine = None
        self._state: bool | None = None  # None = pas encore tenté, bool = dispo ?

    @property
    def available(self) -> bool:
        """True si la passe NER est chargée (sans re-déclencher le chargement)."""
        return self._state is True

    def anonymize(self, text: str) -> str:
        # 1. Passe regex — toujours disponible.
        text = self._regex.anonymize(text)
        # 2. Passe NER — si Presidio + modèle spaCy sont présents.
        if self._ensure_loaded():
            text = self._ner_pass(text)
        return text

    def _ensure_loaded(self) -> bool:
        """Charge Presidio une seule fois ; mémorise l'échec éventuel."""
        if self._state is not None:
            return self._state
        if not self._enabled:
            self._state = False
            logger.info(
                "Passe NER Presidio désactivée (PRESIDIO_ENABLED=false) — "
                "anonymisation regex seule."
            )
            return False
        try:
            self._build_engine()
            self._state = True
            logger.info("Presidio NER activé (modèle %s)", self._spacy_model)
        except Exception as exc:  # noqa: BLE001 — repli assumé, tout échec = regex seule
            self._state = False
            logger.warning(
                "Presidio indisponible (%s) — repli sur l'anonymisation regex seule.",
                exc,
            )
        return self._state

    def _build_engine(self) -> None:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "fr", "model_name": self._spacy_model}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()

        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)
        self._analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)
        self._anonymizer_engine = AnonymizerEngine()

    def _ner_pass(self, text: str) -> str:
        from presidio_anonymizer.entities import OperatorConfig

        results = self._analyzer.analyze(
            text=text,
            language="fr",
            entities=ENTITIES,
            score_threshold=0.5,
        )
        if not results:
            return text

        operators = {
            ent: OperatorConfig("replace", {"new_value": token})
            for ent, token in ENTITY_TOKEN.items()
        }
        result = self._anonymizer_engine.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        # Selon la version de Presidio, anonymize() renvoie un EngineResult (.text)
        # ou directement la chaîne anonymisée.
        return result.text if hasattr(result, "text") else result
