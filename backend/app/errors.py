"""Hiérarchie d'exceptions métier → codes HTTP cohérents.

Chaque exception porte un `code` stable (pour le front) et un `status_code`.
"""
from __future__ import annotations


class AppError(Exception):
    """Erreur de base de l'application."""

    status_code = 500
    code = "internal_error"


# --- Requêtes / upload ---
class InvalidFileTypeError(AppError):
    status_code = 415
    code = "invalid_file_type"


class UploadTooLargeError(AppError):
    status_code = 413
    code = "upload_too_large"


# --- Ingestion PDF ---
class PdfError(AppError):
    code = "pdf_error"


class PdfNotFoundError(PdfError):
    status_code = 404
    code = "pdf_not_found"


class PdfEncryptedError(PdfError):
    status_code = 422
    code = "pdf_encrypted"


class PdfCorruptedError(PdfError):
    status_code = 422
    code = "pdf_corrupted"


class PdfNoTextLayerError(PdfError):
    status_code = 422
    code = "pdf_no_text_layer"


# --- LLM ---
class LlmError(AppError):
    status_code = 502
    code = "llm_error"


class LlmAuthError(LlmError):
    status_code = 500
    code = "llm_auth_error"


class LlmRateLimitError(LlmError):
    status_code = 429
    code = "llm_rate_limit"


class LlmTimeoutError(LlmError):
    status_code = 504
    code = "llm_timeout"


class LlmOutputError(LlmError):
    code = "llm_invalid_output"
