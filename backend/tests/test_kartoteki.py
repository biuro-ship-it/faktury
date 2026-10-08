"""Kartoteki: kontrahenci, towary (z surowcami) i pracownicy.

Dane nie są czyszczone między testami (dziennik zdarzeń blokuje DELETE), więc każdy test szuka
swoich rekordów po unikalnym fragmencie nazwy."""

import pytest
from sqlalchemy import select

from app.auth.firebase import DaneTokenu
from app.models import DziennikZdarzen, Uzytkownik
from tests.test_api_logowanie import klient, naglowek, tokeny, uzytkownik, wpisy_dziennika  # noqa: F401 — fikstury
from tests.test_ustawienia import poprawny_nip

U = naglowek("dobry")


@pytest.fixture
def zwykly(fabryka, unikalny, tokeny):  # noqa: F811
    """Zwykły użytkownik (nie admin) — kartoteki mają mu pozwalać na pracę."""
    email = f"ola-{unikalny}@pluszek.pl"
    with fabryka.begin() as sesja:
        sesja.add(Uzytkownik(email=email, imie="Ola", rola="uzytkownik"))
    tokeny["zwykly"] = DaneTokenu(uid=f"u-{unikalny}", email=email, email_zweryfikowany=True, metoda_logowania="google.com")


def kontrahent(unikalny: str, **nadpisz) -> dict:
    return {"nazwa": f"Firma {unikalny}", "nip": poprawny_nip(), "kod_pocztowy": "00-001", **nadpisz}


def towar(unikalny: str, **nadpisz) -> dict:
    return {"symbol": f"T-{unikalny}".lower(), "nazwa": f"Towar {unikalny}", "stawka_vat_kod": "23", **nadpisz}


# ------------------------------------------------------------------ dostęp

def test_kartoteki_wymagaja_logowania(klient):  # noqa: F811
    for sciezka in ("kontrahenci", "towary", "pracownicy"):
        assert klient.get(f"/api/kartoteki/{sciezka}").status_code == 401


def test_zwykly_uzytkownik_prowadzi_kartoteki(klient, zwykly, unikalny):  # noqa: F811
    r = klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny), headers=naglowek("zwykly"))
    assert r.status_code == 201


# ------------------------------------------------------------------ kontrahenci

def test_dodanie_kontrahenta_normalizuje_dane(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    nip = poprawny_nip()
    dane = kontrahent(unikalny, nip=f"PL {nip[:3]}-{nip[3:6]}-{nip[6:8]}-{nip[8:]}", kraj="pl", jest_dostawca=True)
    r = klient.post("/api/kartoteki/kontrahenci", json=dane, headers=U)
    assert r.status_code == 201, r.text
    k = r.json()
    assert (k["nip"], k["kraj"], k["jest_odbiorca"], k["jest_dostawca"]) == (nip, "PL", True, True)
    assert k["aktywny"] is True
    wpis = [w for w in wpisy_dziennika(fabryka, "kontrahent.dodany") if w.encja_id == k["id"]]
    assert len(wpis) == 1 and wpis[0].uzytkownik_id == uzytkownik.id and wpis[0].po["nip"] == nip


@pytest.mark.parametrize("zla_zmiana, fragment", [
    ({"nip": "1234567890"}, "NIP"),
    ({"regon": "123"}, "REGON"),
    ({"kod_pocztowy": "123"}, "Kod pocztowy"),
    ({"email": "bez-malpy"}, "e-mail"),
    ({"jest_odbiorca": False, "jest_dostawca": False}, "odbiorcą, dostawcą"),
    ({"nazwa": "   "}, "nazwę"),
])
def test_walidacja_kontrahenta(klient, uzytkownik, unikalny, zla_zmiana, fragment):  # noqa: F811
    r = klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny, **zla_zmiana), headers=U)
    assert r.status_code == 422
    assert fragment in str(r.json()["detail"])


def test_nip_jest_unikalny(klient, uzytkownik, unikalny):  # noqa: F811
    dane = kontrahent(unikalny)
    assert klient.post("/api/kartoteki/kontrahenci", json=dane, headers=U).status_code == 201
    r = klient.post("/api/kartoteki/kontrahenci", json={**dane, "nazwa": "Inna nazwa"}, headers=U)
    assert r.status_code == 409 and unikalny in r.json()["detail"]


def test_kontrahenci_bez_nip_moga_sie_powtarzac(klient, uzytkownik, unikalny):  # noqa: F811
    dane = kontrahent(unikalny, nip="", typ="osoba_fizyczna")
    assert klient.post("/api/kartoteki/kontrahenci", json=dane, headers=U).status_code == 201
    assert klient.post("/api/kartoteki/kontrahenci", json=dane, headers=U).status_code == 201


def test_zmiana_kontrahenta_zapisuje_tylko_roznice(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    k = klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny), headers=U).json()
    zmiana = {**{p: v for p, v in k.items() if p != "id"}, "telefon": "600 100 200", "termin_platnosci_dni": 30}
    r = klient.put(f"/api/kartoteki/kontrahenci/{k['id']}", json=zmiana, headers=U)
    assert r.status_code == 200 and r.json()["termin_platnosci_dni"] == 30
    wpis = [w for w in wpisy_dziennika(fabryka, "kontrahent.zmieniony") if w.encja_id == k["id"]]
    assert len(wpis) == 1
    assert wpis[0].przed == {"telefon": "", "termin_platnosci_dni": None}
    assert wpis[0].po == {"telefon": "600 100 200", "termin_platnosci_dni": 30}
    # Zapis bez zmian nie zostawia śladu w dzienniku.
    klient.put(f"/api/kartoteki/kontrahenci/{k['id']}", json=zmiana, headers=U)
    assert len([w for w in wpisy_dziennika(fabryka, "kontrahent.zmieniony") if w.encja_id == k["id"]]) == 1


def test_nip_innego_kontrahenta_przy_edycji_409(klient, uzytkownik, unikalny):  # noqa: F811
    a = klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny), headers=U).json()
    b = klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny + "b"), headers=U).json()
    zmiana = {p: v for p, v in b.items() if p != "id"} | {"nip": a["nip"]}
    assert klient.put(f"/api/kartoteki/kontrahenci/{b['id']}", json=zmiana, headers=U).status_code == 409
    # Własny NIP przy edycji nie jest konfliktem.
    wlasny = {p: v for p, v in b.items() if p != "id"}
    assert klient.put(f"/api/kartoteki/kontrahenci/{b['id']}", json=wlasny, headers=U).status_code == 200


def test_wylaczenie_kontrahenta_i_filtry(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    k = klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny, jest_odbiorca=False, jest_dostawca=True),
                    headers=U).json()
    szukaj = {"q": unikalny, "aktywnosc": "wszystkie"}
    assert klient.get("/api/kartoteki/kontrahenci", params=szukaj | {"rola": "dostawcy"}, headers=U).json()["razem"] == 1
    assert klient.get("/api/kartoteki/kontrahenci", params=szukaj | {"rola": "odbiorcy"}, headers=U).json()["razem"] == 0

    wylaczony = {p: v for p, v in k.items() if p != "id"} | {"aktywny": False}
    assert klient.put(f"/api/kartoteki/kontrahenci/{k['id']}", json=wylaczony, headers=U).status_code == 200
    assert [w for w in wpisy_dziennika(fabryka, "kontrahent.wylaczony") if w.encja_id == k["id"]]
    assert klient.get("/api/kartoteki/kontrahenci", params={"q": unikalny}, headers=U).json()["razem"] == 0
    assert klient.get("/api/kartoteki/kontrahenci", params={"q": unikalny, "aktywnosc": "nie"}, headers=U).json()["razem"] == 1
    # Brak endpointu usuwania — rekordów się nie kasuje.
    assert klient.delete(f"/api/kartoteki/kontrahenci/{k['id']}", headers=U).status_code == 405


def test_wyszukiwanie_po_nip_i_dosłowne_znaki_specjalne(klient, uzytkownik, unikalny):  # noqa: F811
    dane = kontrahent(unikalny, nazwa=f"Pluszek 100% {unikalny}")
    klient.post("/api/kartoteki/kontrahenci", json=dane, headers=U)
    po_nip = klient.get("/api/kartoteki/kontrahenci", params={"q": dane["nip"]}, headers=U).json()
    assert [p["nazwa"] for p in po_nip["pozycje"]] == [dane["nazwa"]]
    # „%” i „_” szukamy dosłownie, nie jako wzorca LIKE.
    assert klient.get("/api/kartoteki/kontrahenci", params={"q": "100% " + unikalny}, headers=U).json()["razem"] == 1
    assert klient.get("/api/kartoteki/kontrahenci", params={"q": "%" + unikalny[:3] + "_"}, headers=U).json()["razem"] == 0


def test_paginacja_kontrahentow(klient, uzytkownik, unikalny):  # noqa: F811
    for i in range(3):
        klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny, nazwa=f"Seria {unikalny} {i}", nip=""), headers=U)
    strona = klient.get("/api/kartoteki/kontrahenci", params={"q": f"Seria {unikalny}", "limit": 2, "offset": 2}, headers=U).json()
    assert strona["razem"] == 3 and [p["nazwa"] for p in strona["pozycje"]] == [f"Seria {unikalny} 2"]


def test_nieistniejacy_kontrahent_404(klient, uzytkownik):  # noqa: F811
    assert klient.get("/api/kartoteki/kontrahenci/999999999", headers=U).status_code == 404


# ------------------------------------------------------------------ towary

def test_dodanie_towaru(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    r = klient.post("/api/kartoteki/towary", json=towar(unikalny, typ="surowiec", jm="kg", cena_sprzedazy_netto=1250,
                                                         gtu="gtu_03"), headers=U)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["symbol"] == f"T-{unikalny}".upper()  # symbol zawsze wielkimi literami
    assert (t["typ"], t["jm"], t["cena_sprzedazy_netto"], t["gtu"]) == ("surowiec", "kg", 1250, "GTU_03")
    assert t["magazynowy"] is True and "23%" in t["stawka_vat_nazwa"]
    assert [w for w in wpisy_dziennika(fabryka, "towar.dodany") if w.encja_id == t["id"]]


def test_usluga_nie_jest_magazynowa(klient, uzytkownik, unikalny):  # noqa: F811
    t = klient.post("/api/kartoteki/towary", json=towar(unikalny, typ="usluga"), headers=U).json()
    assert t["magazynowy"] is False


def test_cena_musi_byc_w_groszach_jako_liczba_calkowita(klient, uzytkownik, unikalny):  # noqa: F811
    for zla in (12.5, -1, "dużo"):
        r = klient.post("/api/kartoteki/towary", json=towar(unikalny, cena_sprzedazy_netto=zla), headers=U)
        assert r.status_code == 422, zla


@pytest.mark.parametrize("zla_zmiana, fragment", [
    ({"symbol": "z ogonkiem ł"}, "Symbol"),
    ({"gtu": "GTU_14"}, "GTU"),
    ({"ean": "123"}, "EAN"),
    ({"stawka_vat_kod": "99"}, "stawk"),
    ({"typ": "cos"}, "typ"),
])
def test_walidacja_towaru(klient, uzytkownik, unikalny, zla_zmiana, fragment):  # noqa: F811
    r = klient.post("/api/kartoteki/towary", json=towar(unikalny, **zla_zmiana), headers=U)
    assert r.status_code == 422
    assert fragment.lower() in str(r.json()["detail"]).lower()


def test_symbol_towaru_jest_unikalny_bez_wzgledu_na_wielkosc_liter(klient, uzytkownik, unikalny):  # noqa: F811
    assert klient.post("/api/kartoteki/towary", json=towar(unikalny), headers=U).status_code == 201
    r = klient.post("/api/kartoteki/towary", json=towar(unikalny).copy() | {"symbol": f"t-{unikalny}".upper()}, headers=U)
    assert r.status_code == 409


def test_wylaczona_stawka_vat_nie_trafi_na_nowy_towar(klient, uzytkownik, unikalny):  # noqa: F811
    # „0 KR” jest wyłączona w stawkach startowych.
    r = klient.post("/api/kartoteki/towary", json=towar(unikalny, stawka_vat_kod="0 KR"), headers=U)
    assert r.status_code == 422 and "wyłączona" in r.json()["detail"]


def test_zmiana_towaru_i_filtr_typu(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    t = klient.post("/api/kartoteki/towary", json=towar(unikalny, typ="surowiec"), headers=U).json()
    dane = {p: v for p, v in t.items() if p not in ("id", "stawka_vat_nazwa", "magazynowy")}
    r = klient.put(f"/api/kartoteki/towary/{t['id']}", json=dane | {"nazwa": "Nowa nazwa " + unikalny, "cena_sprzedazy_netto": 999},
                   headers=U)
    assert r.status_code == 200
    wpis = [w for w in wpisy_dziennika(fabryka, "towar.zmieniony") if w.encja_id == t["id"]]
    assert wpis[0].po == {"nazwa": "Nowa nazwa " + unikalny, "cena_sprzedazy_netto": 999}
    assert wpis[0].przed["cena_sprzedazy_netto"] is None

    szukaj = {"q": unikalny}
    assert klient.get("/api/kartoteki/towary", params=szukaj | {"typ": "surowiec"}, headers=U).json()["razem"] == 1
    assert klient.get("/api/kartoteki/towary", params=szukaj | {"typ": "usluga"}, headers=U).json()["razem"] == 0


def test_wylaczenie_towaru(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    t = klient.post("/api/kartoteki/towary", json=towar(unikalny), headers=U).json()
    dane = {p: v for p, v in t.items() if p not in ("id", "stawka_vat_nazwa", "magazynowy")} | {"aktywny": False}
    assert klient.put(f"/api/kartoteki/towary/{t['id']}", json=dane, headers=U).status_code == 200
    assert [w for w in wpisy_dziennika(fabryka, "towar.wylaczony") if w.encja_id == t["id"]]
    assert klient.get("/api/kartoteki/towary", params={"q": unikalny}, headers=U).json()["razem"] == 0


def test_towar_przy_wylaczonej_stawce_mozna_dalej_edytowac(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    """Towar z zapisaną stawką, którą później wyłączono, zachowuje ją (inaczej nie dałoby się go nawet wyłączyć)."""
    from app.models import StawkaVat
    t = klient.post("/api/kartoteki/towary", json=towar(unikalny, stawka_vat_kod="5"), headers=U).json()
    with fabryka.begin() as sesja:
        sesja.get(StawkaVat, "5").aktywna = False
    try:
        dane = {p: v for p, v in t.items() if p not in ("id", "stawka_vat_nazwa", "magazynowy")} | {"aktywny": False}
        assert klient.put(f"/api/kartoteki/towary/{t['id']}", json=dane, headers=U).status_code == 200
    finally:
        with fabryka.begin() as sesja:
            sesja.get(StawkaVat, "5").aktywna = True


# ------------------------------------------------------------------ pracownicy

def pracownik(unikalny: str, **nadpisz) -> dict:
    return {"imie": "Anna", "nazwisko": f"Kowalska{unikalny}", "stanowisko": "Szwaczka", **nadpisz}


def test_dodanie_i_zmiana_pracownika(klient, uzytkownik, fabryka, unikalny):  # noqa: F811
    r = klient.post("/api/kartoteki/pracownicy", json=pracownik(unikalny, data_zatrudnienia="2026-01-15"), headers=U)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["data_zatrudnienia"] == "2026-01-15" and p["aktywny"] is True

    dane = {k: v for k, v in p.items() if k != "id"} | {"data_zwolnienia": "2026-09-30", "aktywny": False}
    assert klient.put(f"/api/kartoteki/pracownicy/{p['id']}", json=dane, headers=U).status_code == 200
    wpis = [w for w in wpisy_dziennika(fabryka, "pracownik.zmieniony") if w.encja_id == p["id"]]
    assert wpis[0].po == {"data_zwolnienia": "2026-09-30", "aktywny": False}
    assert klient.get("/api/kartoteki/pracownicy", params={"q": unikalny}, headers=U).json()["razem"] == 0
    assert klient.get("/api/kartoteki/pracownicy", params={"q": unikalny, "aktywnosc": "wszystkie"}, headers=U).json()["razem"] == 1


def test_walidacja_pracownika(klient, uzytkownik, unikalny):  # noqa: F811
    zle = [
        ({"data_zatrudnienia": "2026-05-01", "data_zwolnienia": "2026-04-01"}, "wcześniejsza"),
        ({"email": "zly"}, "e-mail"),
        ({"imie": "  "}, "imię"),
    ]
    for zmiana, fragment in zle:
        r = klient.post("/api/kartoteki/pracownicy", json=pracownik(unikalny, **zmiana), headers=U)
        assert r.status_code == 422 and fragment in str(r.json()["detail"]), zmiana


def test_pracownicy_sortowani_po_nazwisku(klient, uzytkownik, unikalny):  # noqa: F811
    for nazwisko in ("Żak", "Adamski", "Nowak"):
        klient.post("/api/kartoteki/pracownicy", json=pracownik(unikalny, nazwisko=f"{nazwisko} {unikalny}"), headers=U)
    lista = klient.get("/api/kartoteki/pracownicy", params={"q": unikalny}, headers=U).json()["pozycje"]
    assert [p["nazwisko"].split()[0] for p in lista] == ["Adamski", "Nowak", "Żak"]


# ------------------------------------------------------------------ baza

def test_baza_pilnuje_ograniczen_niezaleznie_od_api(fabryka, unikalny):
    """Niezmienniki siedzą też w bazie — błąd w kodzie API ich nie obejdzie."""
    from sqlalchemy.exc import IntegrityError

    from app.models import Kontrahent, Towar

    with pytest.raises(IntegrityError), fabryka.begin() as sesja:
        sesja.add(Kontrahent(nazwa="x", jest_odbiorca=False, jest_dostawca=False))
    with pytest.raises(IntegrityError), fabryka.begin() as sesja:
        sesja.add(Towar(symbol=f"X-{unikalny}", nazwa="x", typ="surowiec", stawka_vat_kod="23", cena_sprzedazy_netto=-5))
    with pytest.raises(IntegrityError), fabryka.begin() as sesja:
        sesja.add(Towar(symbol=f"Y-{unikalny}", nazwa="x", typ="surowiec", stawka_vat_kod="nie-ma"))
    with fabryka() as sesja:  # nic nie zostało zapisane
        assert sesja.scalar(select(DziennikZdarzen.id).where(DziennikZdarzen.opis == f"X-{unikalny}")) is None
