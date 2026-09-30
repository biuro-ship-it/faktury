"""Weryfikacja tokenu na prawdziwie podpisanych JWT (własny klucz testowy zamiast Google)."""

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt

from app.auth.firebase import BladTokenu, BrakKonfiguracji, weryfikuj_token

PROJEKT = "pluszek-ksiegowosc-test"


def _klucz() -> tuple[bytes, bytes]:
    prywatny = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_prywatny = prywatny.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    pem_publiczny = prywatny.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem_prywatny, pem_publiczny


PRYWATNY, PUBLICZNY = _klucz()
OBCY_PRYWATNY, _ = _klucz()
CERTYFIKATY = {"klucz1": PUBLICZNY.decode()}


def _token(klucz: bytes = PRYWATNY, **zmiany) -> str:
    teraz = int(time.time())
    dane = {
        "iss": f"https://securetoken.google.com/{PROJEKT}",
        "aud": PROJEKT,
        "sub": "uid-123",
        "iat": teraz,
        "exp": teraz + 3600,
        "email": "Info@Pluszek.pl",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    dane.update(zmiany)
    dane = {k: v for k, v in dane.items() if v is not None}
    podpisujacy = crypt.RSASigner.from_string(klucz, key_id="klucz1")
    return jwt.encode(podpisujacy, dane).decode()


def test_poprawny_token():
    dane = weryfikuj_token(_token(), PROJEKT, CERTYFIKATY)
    assert dane.uid == "uid-123"
    assert dane.email == "info@pluszek.pl"  # normalizacja do małych liter
    assert dane.email_zweryfikowany is True
    assert dane.metoda_logowania == "google.com"


def test_niezweryfikowany_email_jest_przekazany_dalej():
    assert weryfikuj_token(_token(email_verified=False), PROJEKT, CERTYFIKATY).email_zweryfikowany is False


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: _token(aud="inny-projekt"), id="inny-aud"),
        pytest.param(lambda: _token(iss="https://securetoken.google.com/inny-projekt"), id="inny-iss"),
        pytest.param(lambda: _token(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200), id="wygasly"),
        pytest.param(lambda: _token(klucz=OBCY_PRYWATNY), id="obcy-podpis"),
        pytest.param(lambda: _token(email=None), id="bez-emaila"),
        pytest.param(lambda: _token(sub=""), id="bez-uid"),
        pytest.param(lambda: "to.nie.jest-token", id="smieci"),
    ],
)
def test_odrzucone_tokeny(token):
    with pytest.raises(BladTokenu):
        weryfikuj_token(token(), PROJEKT, CERTYFIKATY)


def test_brak_konfiguracji_projektu():
    with pytest.raises(BrakKonfiguracji):
        weryfikuj_token(_token(), "", CERTYFIKATY)
