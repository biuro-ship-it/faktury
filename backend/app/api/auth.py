from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.firebase import DaneTokenu
from app.auth.zaleznosci import KOMUNIKATY_ODMOWY, ocen_dostep, pobierz_dane_tokenu, pobierz_uzytkownika
from app.core.dziennik import zapisz_zdarzenie
from app.db import pobierz_sesje
from app.models import Uzytkownik

router = APIRouter(prefix="/api", tags=["logowanie"])


class Profil(BaseModel):
    id: int
    email: str
    imie: str
    rola: str


def _profil(u: Uzytkownik) -> Profil:
    return Profil(id=u.id, email=u.email, imie=u.imie, rola=u.rola)


@router.post("/auth/logowanie", response_model=Profil)
def zaloguj(
    dane: DaneTokenu = Depends(pobierz_dane_tokenu),
    sesja: Session = Depends(pobierz_sesje),
) -> Profil:
    """Wołane przez front raz, zaraz po zalogowaniu Google. Zapisuje logowanie
    (także nieudane) w dzienniku zdarzeń."""
    uzytkownik, powod = ocen_dostep(sesja, dane)
    if powod is not None:
        zapisz_zdarzenie(
            sesja,
            "logowanie.odmowa",
            uzytkownik_id=uzytkownik.id if uzytkownik else None,
            opis=f"{dane.email}: {powod}",
        )
        sesja.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, KOMUNIKATY_ODMOWY[powod])
    assert uzytkownik is not None

    przed = {"firebase_uid": uzytkownik.firebase_uid}
    uzytkownik.firebase_uid = dane.uid
    uzytkownik.ostatnie_logowanie = datetime.now(UTC)
    zapisz_zdarzenie(
        sesja,
        "logowanie",
        uzytkownik_id=uzytkownik.id,
        encja="uzytkownik",
        encja_id=uzytkownik.id,
        # Zmiana UID oznacza np. usunięte i odtworzone konto w Firebase — warto to widzieć.
        przed=przed if przed["firebase_uid"] != dane.uid else None,
        po={"firebase_uid": dane.uid} if przed["firebase_uid"] != dane.uid else None,
    )
    sesja.commit()
    return _profil(uzytkownik)


@router.get("/me", response_model=Profil)
def ja(uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika)) -> Profil:
    return _profil(uzytkownik)
