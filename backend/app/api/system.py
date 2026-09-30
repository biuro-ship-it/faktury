from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.zaleznosci import pobierz_uzytkownika
from app.db import pobierz_sesje

# Brak publicznych endpointów (PLAN, sekcja 4) — nawet test zdrowia wymaga zalogowania.
router = APIRouter(prefix="/api", tags=["system"], dependencies=[Depends(pobierz_uzytkownika)])


@router.get("/zdrowie")
def zdrowie(sesja: Session = Depends(pobierz_sesje)) -> dict[str, str]:
    sesja.execute(text("SELECT 1"))
    return {"status": "ok"}
