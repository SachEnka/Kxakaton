from fastapi import APIRouter, Depends, HTTPException

from app.integrations.egrul_nalog import EgrulLookupError
from app.integrations.registry import company_profile
from app.models import User
from app.security import require_client

router = APIRouter(prefix="/registry", tags=["registry"])


@router.get("/{inn}")
def lookup_inn(inn: str, _: User = Depends(require_client)) -> dict:
    normalized = inn.strip()
    if not (normalized.isdigit() and len(normalized) in {10, 12}):
        raise HTTPException(status_code=400, detail="ИНН состоит из 10 цифр для организации или 12 цифр для ИП")
    try:
        return company_profile(normalized)
    except EgrulLookupError as exc:
        status = 404 if exc.code == "not_found" else 503
        raise HTTPException(status_code=status, detail=str(exc)) from exc
