import random
import string
from datetime import date

import pytest
from sqlalchemy import select

from app.auth.firebase import DaneTokenu
from app.core import biala_lista
from app.core.numeracja import przydziel_numer
from app.core.walidacja import BladWalidacji, formatuj_iban, normalizuj_iban, normalizuj_nip
from app.models import DziennikZdarzen, Uzytkownik
from tests.test_api_logowanie import klient, naglowek, tokeny, uzytkownik  # noqa: F401 — fikstury

ADMIN = naglowek("dobry")
ZWYKLY = naglowek("zwykly")


def poprawny_nip() -> str:
    while True:
        cyfry = [random.randint(0, 9) for _ in range(9)]
        kontrolna = sum(c * w for c, w in zip(cyfry, (6, 5, 7, 2, 3, 4, 5, 6, 7), strict=True)) % 11
        if kontrolna != 10:
            return "".join(map(str, cyfry)) + str(kontrolna)


def poprawny_nrb() -> str:
    reszta = "".join(random.choices(string.digits, k=24))
    kontrolne = 98 - int(reszta + "252100") % 97  # "PL" = 25 21
    return f"{kontrolne:02d}{reszta}"


def unikalna_waluta() -> str:
    return "Q" + "".join(random.choices(string.ascii_uppercase, k=2))


@pytest.fixture
def zwykly(fabryka, unikalny, tokeny):  # noqa: F811
    email = f"jan-{unikalny}@pluszek.pl"
    with fabryka.begin() as sesja:
        sesja.add(Uzytkownik(email=email, imie="Jan", rola="uzytkownik"))
    tokeny["zwykly"] = DaneTokenu(uid="u2", email=email, email_zweryfikowany=True, metoda_logowania="google.com")


# ------------------------------------------------------------------ walidacja

def test_nip():
    nip = poprawny_nip()
    assert normalizuj_nip(f"PL {nip[:3]}-{nip[3:6]}-{nip[6:8]}-{nip[8:]}") == nip
    zly = nip[:9] + str((int(nip[9]) + 1) % 10)
    for bledny in (zly, "123", "abcdefghij"):
        with pytest.raises(BladWalidacji):
            normalizuj_nip(bledny)


def test_iban():
    assert normalizuj_iban("61 1090 1014 0000 0712 1981 2874") == "PL61109010140000071219812874"
    assert normalizuj_iban("pl61109010140000071219812874") == "PL61109010140000071219812874"
    assert formatuj_iban("PL61109010140000071219812874") == "PL61 1090 1014 0000 0712 1981 2874"
    for bledny in ("62109010140000071219812874", "1234", "PL6110901014000007121981287"):
        with pytest.raises(BladWalidacji):
            normalizuj_iban(bledny)


# ------------------------------------------------------------------ Biała Lista

def test_rozbij_adres():
    assert biala_lista.rozbij_adres("UL. KWIATOWA 1/2, 00-001 WARSZAWA") == ("UL. KWIATOWA 1/2", "00-001", "WARSZAWA")
    assert biala_lista.rozbij_adres("RYNEK 5 34-100 WADOWICE") == ("RYNEK 5", "34-100", "WADOWICE")
    assert biala_lista.rozbij_adres("dziwny adres") == ("dziwny adres", "", "")


def test_odpowiedz_bialej_listy():
    dane = biala_lista.z_odpowiedzi({"result": {"subject": {
        "name": "PLUSZEK SP. Z O.O.", "nip": "1234563218", "regon": "123456785", "statusVat": "Czynny",
        "workingAddress": "UL. KWIATOWA 1, 00-001 WARSZAWA", "accountNumbers": ["61109010140000071219812874"],
    }}})
    assert (dane.nazwa, dane.adres_ulica, dane.kod_pocztowy, dane.miejscowosc) == (
        "PLUSZEK SP. Z O.O.", "UL. KWIATOWA 1", "00-001", "WARSZAWA")
    assert dane.konta == ["61109010140000071219812874"]
    with pytest.raises(biala_lista.BladBialejListy):
        biala_lista.z_odpowiedzi({"result": {"subject": None}})


def test_endpoint_bialej_listy(klient, uzytkownik, monkeypatch):  # noqa: F811
    nip = poprawny_nip()
    monkeypatch.setattr(biala_lista, "pobierz", lambda n: biala_lista.DanePodmiotu(
        nazwa="X", nip=n, regon="", status_vat="Czynny", konta=["61109010140000071219812874"]))
    odp = klient.get(f"/api/ustawienia/biala-lista/{nip}", headers=ADMIN)
    assert odp.status_code == 200
    assert odp.json()["konta"] == ["PL61 1090 1014 0000 0712 1981 2874"]
    assert klient.get("/api/ustawienia/biala-lista/123", headers=ADMIN).status_code == 422

    def limit(_):
        raise biala_lista.BladBialejListy("limit")
    monkeypatch.setattr(biala_lista, "pobierz", limit)
    assert klient.get(f"/api/ustawienia/biala-lista/{nip}", headers=ADMIN).status_code == 502


# ------------------------------------------------------------------ firma

def test_firma_zapis_walidacja_i_dziennik(klient, fabryka, uzytkownik, unikalny):  # noqa: F811
    nip = poprawny_nip()
    dane = {"nazwa": f"Pluszek {unikalny}", "nip": f"{nip[:3]}-{nip[3:]}", "kod_pocztowy": "34-100",
            "miejscowosc": "Wadowice", "termin_platnosci_dni": 7, "forma_platnosci": "przelew"}
    odp = klient.put("/api/ustawienia/firma", headers=ADMIN, json=dane)
    assert odp.status_code == 200
    assert odp.json()["nip"] == nip and odp.json()["termin_platnosci_dni"] == 7
    assert klient.get("/api/ustawienia/firma", headers=ADMIN).json()["nazwa"] == f"Pluszek {unikalny}"

    # Ten sam zapis drugi raz = brak zmian = brak nowego wpisu w dzienniku.
    klient.put("/api/ustawienia/firma", headers=ADMIN, json=dane)
    with fabryka() as sesja:
        wpisy = sesja.scalars(select(DziennikZdarzen).where(DziennikZdarzen.akcja == "firma.zmieniona")).all()
    ostatni = [w for w in wpisy if (w.po or {}).get("nazwa") == f"Pluszek {unikalny}"]
    assert len(ostatni) == 1

    for zle in ({"nip": "1234567890"}, {"kod_pocztowy": "34100"}, {"email": "bez-malpy"},
                {"regon": "12"}, {"termin_platnosci_dni": 400}, {"forma_platnosci": "barter"}):
        assert klient.put("/api/ustawienia/firma", headers=ADMIN, json={**dane, **zle}).status_code == 422


def test_zmiany_tylko_dla_admina(klient, uzytkownik, zwykly):  # noqa: F811
    assert klient.get("/api/ustawienia/firma", headers=ZWYKLY).status_code == 200
    assert klient.put("/api/ustawienia/firma", headers=ZWYKLY, json={}).status_code == 403
    assert klient.post("/api/ustawienia/konta", headers=ZWYKLY,
                       json={"nazwa": "x", "numer": poprawny_nrb()}).status_code == 403
    assert klient.patch("/api/ustawienia/stawki-vat/8", headers=ZWYKLY, json={"aktywna": False}).status_code == 403


# ------------------------------------------------------------------ konta

def test_konta_domyslne_na_walute(klient, uzytkownik):  # noqa: F811
    waluta = unikalna_waluta()
    pierwsze = klient.post("/api/ustawienia/konta", headers=ADMIN,
                           json={"nazwa": "Główne", "numer": poprawny_nrb(), "waluta": waluta}).json()
    assert pierwsze["domyslne"] is True  # pierwsze konto w walucie staje się domyślne
    assert pierwsze["numer"].startswith("PL") and " " in pierwsze["numer_sformatowany"]

    drugie = klient.post("/api/ustawienia/konta", headers=ADMIN,
                         json={"nazwa": "Drugie", "numer": poprawny_nrb(), "waluta": waluta, "domyslne": True}).json()
    konta = {k["id"]: k for k in klient.get("/api/ustawienia/konta", headers=ADMIN).json()}
    assert konta[drugie["id"]]["domyslne"] and not konta[pierwsze["id"]]["domyslne"]

    wylaczone = klient.patch(f"/api/ustawienia/konta/{drugie['id']}", headers=ADMIN, json={"aktywne": False}).json()
    assert wylaczone["aktywne"] is False and wylaczone["domyslne"] is False
    assert klient.patch(f"/api/ustawienia/konta/{drugie['id']}", headers=ADMIN,
                        json={"domyslne": True}).status_code == 422


def test_konta_bledy(klient, uzytkownik):  # noqa: F811
    numer = poprawny_nrb()
    assert klient.post("/api/ustawienia/konta", headers=ADMIN, json={"nazwa": "A", "numer": numer,
                                                                     "waluta": unikalna_waluta()}).status_code == 201
    assert klient.post("/api/ustawienia/konta", headers=ADMIN, json={"nazwa": "B", "numer": numer}).status_code == 409
    zly = numer[:2] + str((int(numer[2]) + 1) % 10) + numer[3:]
    assert klient.post("/api/ustawienia/konta", headers=ADMIN, json={"nazwa": "C", "numer": zly}).status_code == 422
    assert klient.patch("/api/ustawienia/konta/999999999", headers=ADMIN, json={"nazwa": "x"}).status_code == 404


# ------------------------------------------------------------------ stawki VAT

def test_stawki_vat(klient, uzytkownik):  # noqa: F811
    stawki = {s["kod"]: s for s in klient.get("/api/ustawienia/stawki-vat", headers=ADMIN).json()}
    assert {"23", "8", "5", "zw", "0 KR"} <= set(stawki)
    assert stawki["zw"]["procent"] is None
    domyslna = next(k for k, s in stawki.items() if s["domyslna"])

    assert klient.patch(f"/api/ustawienia/stawki-vat/{domyslna}", headers=ADMIN,
                        json={"aktywna": False}).status_code == 422
    try:
        assert klient.patch("/api/ustawienia/stawki-vat/8", headers=ADMIN, json={"domyslna": True}).json()["domyslna"]
        stawki = {s["kod"]: s for s in klient.get("/api/ustawienia/stawki-vat", headers=ADMIN).json()}
        assert [k for k, s in stawki.items() if s["domyslna"]] == ["8"]
    finally:
        klient.patch(f"/api/ustawienia/stawki-vat/{domyslna}", headers=ADMIN, json={"domyslna": True})


# ------------------------------------------------------------------ serie numeracji

def test_serie(klient, fabryka, uzytkownik, unikalny):  # noqa: F811
    odp = klient.post("/api/ustawienia/serie/podglad", headers=ADMIN,
                      json={"wzorzec": "FV/{nr}/{MM}/{RRRR}", "okres_resetu": "miesiac"})
    assert odp.json()["przyklad"] == f"FV/1/{date.today():%m/%Y}"
    assert klient.post("/api/ustawienia/serie/podglad", headers=ADMIN,
                       json={"wzorzec": "FV/{nr}", "okres_resetu": "miesiac"}).status_code == 422

    kod = f"s{unikalny}"
    nowa = {"kod": kod, "typ_dokumentu": "faktura_sprzedazy", "nazwa": "Faktury",
            "wzorzec": "FV/{nr}/{MM}/{RRRR}", "okres_resetu": "miesiac"}
    seria = klient.post("/api/ustawienia/serie", headers=ADMIN, json=nowa).json()
    assert seria["kod"] == kod.upper() and seria["uzyta"] is False
    assert klient.post("/api/ustawienia/serie", headers=ADMIN, json=nowa).status_code == 409
    assert klient.post("/api/ustawienia/serie", headers=ADMIN,
                       json={**nowa, "kod": f"x{unikalny}", "wzorzec": "FV/{nr}"}).status_code == 422
    assert klient.post("/api/ustawienia/serie", headers=ADMIN,
                       json={**nowa, "kod": f"y{unikalny}", "typ_dokumentu": "paragon"}).status_code == 422

    with fabryka.begin() as sesja:
        przydziel_numer(sesja, kod.upper(), date.today())
    zmieniona = klient.patch(f"/api/ustawienia/serie/{seria['id']}", headers=ADMIN, json={"aktywna": False}).json()
    assert zmieniona["aktywna"] is False and zmieniona["uzyta"] is True
