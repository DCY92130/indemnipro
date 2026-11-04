"""Point d'entrée FastAPI du backend ProIndemni.

Lancement : `uvicorn app.main:app --reload` (depuis le dossier `backend/`).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import AppError, InvalidFileTypeError, UploadTooLargeError
from app.schemas import AuditResponse, Orientation, TextInput
from app.services.audit import AuditService
from app.services.orientation import orienter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("proindemni")

settings = get_settings()

app = FastAPI(title="ProIndemni — Audit de contrat multirisque pro", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 Mo

# Le service est construit à la première requête : si la clé API est absente,
# le démarrage ne plante pas et `/health` le signale clairement.
_service: AuditService | None = None


def _get_service() -> AuditService:
    global _service
    if _service is None:
        _service = AuditService(settings)
    return _service


@app.exception_handler(AppError)
async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


@app.exception_handler(Exception)
async def _unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erreur interne non gérée : %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Erreur interne."}},
    )


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "llm_configured": settings.is_configured,
        "model": settings.deepseek_model if settings.is_configured else None,
    }


@app.post("/audit", response_model=AuditResponse)
async def audit_pdf(file: UploadFile = File(...)) -> AuditResponse:
    """Reçoit un PDF de contrat, renvoie l'audit factuel + l'aiguillage."""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError("Seuls les fichiers PDF sont acceptés.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError("Fichier trop volumineux (max 25 Mo).")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        audit = await _get_service().audit_file(tmp_path)
        return AuditResponse(audit=audit, orientation=Orientation(**orienter(audit)))
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


@app.post("/audit/text", response_model=AuditResponse)
async def audit_text(payload: TextInput) -> AuditResponse:
    """Audite un texte brut (endpoint de développement / tests sans PDF)."""
    audit = await _get_service().audit_text(payload.text)
    return AuditResponse(audit=audit, orientation=Orientation(**orienter(audit)))
