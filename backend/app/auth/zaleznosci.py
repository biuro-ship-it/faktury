import logging

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.firebase import BladTokenu, BrakKonfiguracji, DaneTokenu, weryfikuj_token
from app.config import ustawienia
from app.db import pobierz_sesje
from app.models import Uzytkownik

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

KOMUNIKATY_ODMOWY = {
    "email_niezweryfikowany": "Adres e-mail konta Google nie jest zweryfikowany.",
    "niedozwolona_metoda_logowania": "Dozwolone jest tylko logowanie kontem Google.",
    "brak_na_liscie": "To konto nie ma dostępu do aplikacji.",
    "konto_nieaktywne": "To konto zostało wyłączone.",
}


def pobierz_dane_tokenu(
    poswiadczenia: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> DaneTokenu:
    if poswiadczenia is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Brak tokenu — zaloguj się")
    try:
        return weryfikuj_token(poswiadczenia.credentials, ustawienia().firebase_project_id)
    except BladTokenu as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    except BrakKonfiguracji as e:
        logger.error("%s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Logowanie nie jest skonfigurowane") from e
    except requests.RequestException as e:
        logger.error("Nie udało się pobrać certyfikatów Google: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Serwer nie może połączyć się z Google — spróbuj ponownie"
        ) from e


def ocen_dostep(sesja: Session, dane: DaneTokenu) -> tuple[Uzytkownik | None, str | None]:
    """Zwraca (użytkownik, None) gdy dostęp jest dozwolony, albo (użytkownik|None, powód)."""
    if not dane.email_zweryfikowany:
        return None, "email_niezweryfikowany"
    if dane.metoda_logowania != "google.com":
        return None, "niedozwolona_metoda_logowania"
    uzytkownik = sesja.scalar(select(Uzytkownik).where(Uzytkownik.email == dane.email))
    if uzytkownik is None:
        return None, "brak_na_liscie"
    if not uzytkownik.aktywny:
        return uzytkownik, "konto_nieaktywne"
    return uzytkownik, None


def pobierz_uzytkownika(
    dane: DaneTokenu = Depends(pobierz_dane_tokenu),
    sesja: Session = Depends(pobierz_sesje),
) -> Uzytkownik:
    """Allowlista sprawdzana przy KAŻDYM żądaniu — wyłączenie konta działa od razu."""
    uzytkownik, powod = ocen_dostep(sesja, dane)
    if powod is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, KOMUNIKATY_ODMOWY[powod])
    assert uzytkownik is not None
    return uzytkownik


def wymagaj_admina(uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika)) -> Uzytkownik:
    if uzytkownik.rola != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wymagane uprawnienia administratora")
    return uzytkownik
