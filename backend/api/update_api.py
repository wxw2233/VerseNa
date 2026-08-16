from fastapi import APIRouter, HTTPException

from source_update import SourceUpdateError, source_updater
from security_utils import redact_sensitive_text


router = APIRouter(prefix="/api/update", tags=["update"])


@router.get("/status")
async def update_status():
    return await source_updater.status()


@router.post("/check")
async def check_for_updates():
    try:
        return await source_updater.check()
    except SourceUpdateError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=redact_sensitive_text(exc),
        ) from exc


@router.post("/apply")
async def apply_source_update():
    try:
        return await source_updater.apply()
    except SourceUpdateError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=redact_sensitive_text(exc),
        ) from exc
