"""Configuration centralisée de l'application.

Toutes les valeurs sensibles proviennent de variables d'environnement
(ou d'un fichier `.env`), jamais du code.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- API LLM (DeepSeek via SDK OpenAI) ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_temperature: float = 0.0

    # --- Résilience ---
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3
    # Nombre de relances en cas de JSON de sortie non conforme au schéma.
    llm_output_retries: int = 1

    # --- Garde-fou : taille max du texte envoyé au LLM ---
    # deepseek-chat = 64k tokens de contexte (~4 caractères/token en français).
    # On s'arrête à ~180k caractères pour laisser la place au prompt + réponse.
    max_input_chars: int = 180_000

    # --- Serveur ---
    cors_origins: str = "*"

    # --- Anonymisation NER (Presidio / spaCy) ---
    # Modèle spaCy français. `fr_core_news_lg` (571 Mo) = qualité max en local ;
    # `fr_core_news_md` (~45 Mo) est recommandé pour un hébergement léger.
    spacy_model: str = "fr_core_news_lg"
    # Passe NER Presidio : activée par défaut (anonymisation complète en local).
    # Désactivée sur l'hébergement gratuit Render (512 Mo) car le chargement du
    # modèle spaCy + registre Presidio dépasse la RAM disponible et fait tuer le
    # process (OOM). Le repli regex seul reste actif et suffit pour les CGV
    # (document B2B public, champ RGPD réduit).
    presidio_enabled: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
