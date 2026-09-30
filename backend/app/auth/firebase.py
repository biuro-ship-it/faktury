"""Weryfikacja ID tokenu Firebase bez klucza konta serwisowego.

Backend zna tylko FIREBASE_PROJECT_ID i publiczne certyfikaty Google — nie ma żadnych
uprawnień do projektu Firebase (świadoma decyzja, DECISIONS.md 2026-09-30).
"""

import re
import threading
import time
from dataclasses import dataclass

import requests
from google.auth import exceptions as google_exceptions
from google.auth import jwt

URL_CERTYFIKATOW = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
DOPUSZCZALNE_ODCHYLENIE_ZEGARA_S = 10


class BladTokenu(Exception):
    """Token nieprawidłowy, wygasły albo wystawiony dla innego projektu → 401."""


class BrakKonfiguracji(Exception):
    """Serwer nie ma FIREBASE_PROJECT_ID → 503 (to błąd wdrożenia, nie użytkownika)."""


@dataclass(frozen=True)
class DaneTokenu:
    uid: str
    email: str
    email_zweryfikowany: bool
    metoda_logowania: str | None


class _PamiecCertyfikatow:
    """Certyfikaty Google zmieniają się rzadko; trzymamy je tyle, ile każe Cache-Control."""

    def __init__(self) -> None:
        self._blokada = threading.Lock()
        self._certyfikaty: dict[str, str] = {}
        self._wazne_do = 0.0

    def pobierz(self) -> dict[str, str]:
        with self._blokada:
            if self._certyfikaty and time.monotonic() < self._wazne_do:
                return self._certyfikaty
            odpowiedz = requests.get(URL_CERTYFIKATOW, timeout=10)
            odpowiedz.raise_for_status()
            dopasowanie = re.search(r"max-age=(\d+)", odpowiedz.headers.get("Cache-Control", ""))
            czas_zycia = int(dopasowanie.group(1)) if dopasowanie else 3600
            self._certyfikaty = odpowiedz.json()
            self._wazne_do = time.monotonic() + czas_zycia
            return self._certyfikaty


_pamiec_certyfikatow = _PamiecCertyfikatow()


def weryfikuj_token(
    token: str, project_id: str, certyfikaty: dict[str, str] | None = None
) -> DaneTokenu:
    if not project_id:
        raise BrakKonfiguracji("Brak FIREBASE_PROJECT_ID w konfiguracji serwera")
    if certyfikaty is None:
        certyfikaty = _pamiec_certyfikatow.pobierz()

    try:
        # Sprawdza podpis (po kid), exp, iat i aud == project_id.
        dane = jwt.decode(
            token,
            certs=certyfikaty,
            audience=project_id,
            clock_skew_in_seconds=DOPUSZCZALNE_ODCHYLENIE_ZEGARA_S,
        )
    except (ValueError, google_exceptions.GoogleAuthError) as e:
        raise BladTokenu(f"Nieprawidłowy token: {str(e)[:120]}") from e

    if dane.get("iss") != f"https://securetoken.google.com/{project_id}":
        raise BladTokenu("Token wystawiony przez inny projekt")
    uid = dane.get("sub")
    if not isinstance(uid, str) or not uid:
        raise BladTokenu("Token bez identyfikatora użytkownika")
    email = dane.get("email")
    if not isinstance(email, str) or not email:
        raise BladTokenu("Token bez adresu e-mail")

    return DaneTokenu(
        uid=uid,
        email=email.strip().lower(),
        email_zweryfikowany=dane.get("email_verified") is True,
        metoda_logowania=(dane.get("firebase") or {}).get("sign_in_provider"),
    )
