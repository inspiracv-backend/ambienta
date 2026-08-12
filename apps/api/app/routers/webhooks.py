"""Webhooks entrantes de Clerk.

Este router es la unica parte de la API que no exige un JWT: quien llama es
Clerk, no una persona con sesion. La autenticidad se comprueba con la firma
HMAC del payload (protocolo svix), que es tan fuerte como el token —- pero
distinta— y por eso el endpoint vive aparte y no cuelga de `get_tenant_db`.

Tampoco pasa por RLS: al procesar un `user.created` todavia no se sabe de que
tenant es la sesion, porque no hay sesion. El tenant sale del payload firmado.

Spec: openspec/changes/integracion-clerk-auth/design.md §2.4.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError

from ..config import get_settings
from ..deps import get_admin_db
from ..services.clerk_sync import DatosDeClerkInvalidos, procesar_evento

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/clerk", status_code=status.HTTP_200_OK)
async def clerk_webhook(request: Request, db: Session = Depends(get_admin_db)) -> dict:
    """Recibe eventos de usuario de Clerk y los refleja en `users`."""
    settings = get_settings()

    if not settings.clerk_webhook_secret:
        # Sin secreto no hay forma de distinguir a Clerk de cualquiera que
        # conozca la URL. Se responde 503 y no 401 porque el problema es de
        # configuracion del servidor, no del que llama.
        logger.error("Llego un webhook de Clerk pero CLERK_WEBHOOK_SECRET no esta configurado.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El webhook no esta configurado en este entorno.",
        )

    # La firma se calcula sobre los bytes exactos que llegaron. Volver a
    # serializar el JSON parseado cambia espacios y orden de claves, y la
    # verificacion falla por algo que no es un ataque.
    crudo = await request.body()

    try:
        evento = Webhook(settings.clerk_webhook_secret).verify(crudo, dict(request.headers))
    except WebhookVerificationError as exc:
        logger.warning("Webhook de Clerk con firma invalida: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firma invalida.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cuerpo no es JSON valido.",
        ) from exc

    tipo = evento.get("type", "")
    data = evento.get("data") or {}

    try:
        resultado = procesar_evento(db, tipo, data)
        db.commit()
    except DatosDeClerkInvalidos as exc:
        db.rollback()
        # 400 y no 500: el evento venia firmado por Clerk, asi que es autentico,
        # pero le falta algo que solo se puede arreglar en el dashboard de
        # Clerk. Un 5xx haria que Clerk reintentara un payload que nunca va a
        # mejorar solo.
        logger.warning("Evento de Clerk '%s' incompleto: %s", tipo, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        # Aca si conviene el 5xx: fallo algo nuestro y el reintento de Clerk
        # tiene sentido.
        logger.exception("Fallo al procesar el evento de Clerk '%s'", tipo)
        raise

    logger.info("Webhook de Clerk '%s': %s", tipo, resultado)
    return {"ok": True, "event": tipo, "result": resultado}
