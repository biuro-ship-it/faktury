"""Logowanie z allowlistą: kto nie jest aktywnym użytkownikiem w tabeli `uzytkownik`,
nie wejdzie — nawet z poprawnym kontem Google."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import zaleznosci
from app.auth.firebase import BladTokenu, DaneTokenu
from app.db import pobierz_sesje
from app.main import app
from app.models import DziennikZdarzen, Uzytkownik


@pytest.fixture
def tokeny(monkeypatch) -> dict[str, DaneTokenu]:
    """Podmienia weryfikację podpisu (testowana osobno) na słownik token → dane."""
    slownik: dict[str, DaneTokenu] = {}

    def falszywa_weryfikacja(token: str, project_id: str) -> DaneTokenu:
        if token not in slownik:
            raise BladTokenu("nieznany token")
        return slownik[token]

    monkeypatch.setattr(zaleznosci, "weryfikuj_token", falszywa_weryfikacja)
    return slownik


@pytest.fixture
def klient(fabryka) -> TestClient:
    def sesja_testowa():
        with fabryka() as sesja:
            yield sesja

    app.dependency_overrides[pobierz_sesje] = sesja_testowa
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def uzytkownik(fabryka, unikalny, tokeny) -> Uzytkownik:
    email = f"krzysiek-{unikalny}@pluszek.pl"
    with fabryka.begin() as sesja:
        u = Uzytkownik(email=email, imie="Krzysiek", rola="admin")
        sesja.add(u)
    tokeny["dobry"] = DaneTokenu(uid=f"uid-{unikalny}", email=email, email_zweryfikowany=True,
                                 metoda_logowania="google.com")
    return u


def naglowek(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def wpisy_dziennika(fabryka, akcja: str) -> list[DziennikZdarzen]:
    with fabryka() as sesja:
        return list(sesja.scalars(select(DziennikZdarzen).where(DziennikZdarzen.akcja == akcja)))


def test_bez_tokenu_401(klient):
    assert klient.get("/api/me").status_code == 401
    assert klient.get("/api/zdrowie").status_code == 401


def test_zly_token_401(klient, tokeny):
    assert klient.get("/api/me", headers=naglowek("podrobiony")).status_code == 401


def test_poprawne_logowanie(klient, fabryka, uzytkownik):
    odp = klient.post("/api/auth/logowanie", headers=naglowek("dobry"))
    assert odp.status_code == 200
    assert odp.json() == {"id": uzytkownik.id, "email": uzytkownik.email, "imie": "Krzysiek", "rola": "admin"}

    with fabryka() as sesja:
        z_bazy = sesja.get(Uzytkownik, uzytkownik.id)
        assert z_bazy.ostatnie_logowanie is not None
        assert z_bazy.firebase_uid.startswith("uid-")
    assert any(w.uzytkownik_id == uzytkownik.id for w in wpisy_dziennika(fabryka, "logowanie"))

    assert klient.get("/api/me", headers=naglowek("dobry")).json()["email"] == uzytkownik.email
    assert klient.get("/api/zdrowie", headers=naglowek("dobry")).json() == {"status": "ok"}


def test_konto_spoza_listy_nie_wejdzie_i_zostaje_slad(klient, fabryka, tokeny, unikalny):
    obcy = f"obcy-{unikalny}@gmail.com"
    tokeny["obcy"] = DaneTokenu(uid="x", email=obcy, email_zweryfikowany=True, metoda_logowania="google.com")

    assert klient.post("/api/auth/logowanie", headers=naglowek("obcy")).status_code == 403
    assert klient.get("/api/me", headers=naglowek("obcy")).status_code == 403
    odmowy = [w for w in wpisy_dziennika(fabryka, "logowanie.odmowa") if w.opis and obcy in w.opis]
    assert len(odmowy) == 1 and "brak_na_liscie" in odmowy[0].opis


@pytest.mark.parametrize(
    ("zweryfikowany", "metoda"),
    [(False, "google.com"), (True, "password"), (True, "anonymous")],
)
def test_tylko_zweryfikowane_konto_google(klient, tokeny, uzytkownik, zweryfikowany, metoda):
    tokeny["inny"] = DaneTokenu(uid="u", email=uzytkownik.email, email_zweryfikowany=zweryfikowany,
                                metoda_logowania=metoda)
    assert klient.post("/api/auth/logowanie", headers=naglowek("inny")).status_code == 403


def test_wylaczenie_konta_dziala_natychmiast(klient, fabryka, uzytkownik):
    assert klient.get("/api/me", headers=naglowek("dobry")).status_code == 200
    with fabryka.begin() as sesja:
        sesja.get(Uzytkownik, uzytkownik.id).aktywny = False
    assert klient.get("/api/me", headers=naglowek("dobry")).status_code == 403
    assert klient.post("/api/auth/logowanie", headers=naglowek("dobry")).status_code == 403


def test_nieznana_sciezka_api_to_404(klient):
    assert klient.get("/api/nie-ma-takiej").status_code == 404
