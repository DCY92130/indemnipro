"""CLI de test : audite un PDF local et affiche le JSON en sortie.

Usage :  python cli.py contrat.pdf
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.config import get_settings
from app.errors import AppError
from app.services.audit import AuditService


async def run(path: str) -> None:
    service = AuditService(get_settings())
    result = await service.audit_file(path)
    print(result.model_dump_json(indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audite un contrat d'assurance (PDF).")
    parser.add_argument("file", help="Chemin du fichier PDF")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.file))
    except AppError as exc:
        print(f"Erreur [{exc.code}] : {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
