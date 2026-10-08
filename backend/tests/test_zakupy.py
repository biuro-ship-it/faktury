"""Zakupy: faktura zakupu towarów i surowców — cykl szkic → zatwierdzenie → anulowanie, numer faktury dostawcy
(obowiązkowy, bez duplikatów) i ten sam NIEZMIENNIK co w Sprzedaży (zatwierdzonej faktury nie da się zmienić
ani usunąć — także z pominięciem API, numeracja bez dziur, dokument i skutki w jednej transakcji)."""

import threading
from datetime import date, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core import dokumenty as serwis
from app.core.numeracja import utworz_serie
from app.models import Dokument
from tests.test_api_logowanie import klient, naglowek, tokeny, uzytkownik, wpisy_dziennika  # noqa: F401 — fikstury
from tests.test_kartoteki import kontrahent, towar, zwykly  # noqa: F401 — fikstury
from tests.test_sprzedaz import firma  # noqa: F401 — fikstura (uzupełnia dane własnej firmy)

U = naglowek("dobry")
DZIS = date.today()


@pytest.fixture
def seria(fabryka, unikalny) -> int:
    with fabryka.begin() as sesja:
        s = utworz_serie(sesja, kod=f"FZ{unikalny}", typ_dokumentu="faktura_zakupu", nazwa="Testowa zakupu",
                         wzorzec=f"FZ/{unikalny}/{{nr}}/{{MM}}/{{RRRR}}", okres_resetu="miesiac", uzytkownik_id=None)
    return s.id


@pytest.fixture
def seria_sprzedazy(fabryka, unikalny) -> int:
    with fabryka.begin() as sesja:
        s = utworz_serie(sesja, kod=f"FV{unikalny}", typ_dokumentu="faktura_sprzedazy", nazwa="Testowa sprzedaży",
                         wzorzec=f"FV/{unikalny}/{{nr}}/{{MM}}/{{RRRR}}", okres_resetu="miesiac", uzytkownik_id=None)
    return s.id


@pytest.fixture
def dostawca(klient, uzytkownik, unikalny) -> dict:  # noqa: F811
    r = klient.post("/api/kartoteki/kontrahenci", headers=U, json=kontrahent(
        unikalny, jest_odbiorca=False, jest_dostawca=True, termin_platnosci_dni=30))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def surowiec(klient, uzytkownik, unikalny) -> dict:  # noqa: F811
    r = klient.post("/api/kartoteki/towary", headers=U, json=towar(unikalny, typ="surowiec", jm="kg"))
    assert r.status_code == 201, r.text
    return r.json()


def pozycja(towar_id: int | None, **nadpisz) -> dict:
    return {"towar_id": towar_id, "nazwa": "Pianka PU", "jm": "kg", "ilosc": "10", "cena_netto": 1000,
            "stawka_vat_kod": "23", **nadpisz}


_licznik = iter(range(1, 10**6))


def zakup(seria_id: int | None, kontrahent_id: int | None, pozycje: list[dict] | None, **nadpisz) -> dict:
    """Domyślnie każda faktura ma INNY numer dostawcy (inaczej testy zderzałyby się na duplikatach)."""
    return {"seria_id": seria_id, "kontrahent_id": kontrahent_id, "numer_obcy": f"FV/{next(_licznik)}/2026",
            "data_wystawienia": DZIS.isoformat(), "data_zakupu": DZIS.isoformat(), "pozycje": pozycje or [], **nadpisz}


def szkic(klient, dane: dict, naglowki=U) -> dict:  # noqa: F811
    r = klient.post("/api/zakupy/faktury", json=dane, headers=naglowki)
    assert r.status_code == 201, r.text
    return r.json()


def zatwierdz(klient, faktura_id: int) -> dict:  # noqa: F811
    r = klient.post(f"/api/zakupy/faktury/{faktura_id}/zatwierdz", headers=U)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ szkic

def test_zakupy_wymagaja_logowania(klient):  # noqa: F811
    assert klient.get("/api/zakupy/faktury").status_code == 401
    assert klient.get(f"/api/zakupy/rejestr?od={DZIS}&do={DZIS}").status_code == 401


def test_szkic_liczy_sumy_i_termin_dostawcy_bez_numeru(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec):  # noqa: F811
    f = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"], ilosc="3", cena_netto=101)],
                            numer_obcy="  FV 7/2026  "))
    assert f["status"] == "szkic" and f["numer"] is None
    assert f["numer_obcy"] == "FV 7/2026"  # spacje obcięte
    assert (f["suma_netto"], f["suma_vat"], f["suma_brutto"]) == (303, 70, 373)  # VAT od sumy netto w stawce
    assert f["termin_platnosci"] == (DZIS + timedelta(days=30)).isoformat()  # termin dostawcy
    assert f["dostawca_nazwa"] == dostawca["nazwa"] and f["dostawca_nip"] == dostawca["nip"]
    assert f["braki"] == []
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.szkic_utworzony"))


@pytest.mark.parametrize("zmiana, fragment", [
    ({"kontrahent": "odbiorca"}, "dostawca"),       # kontrahent tylko-odbiorca nie może być dostawcą
    ({"pozycja": {"towar_id": None}}, "kartoteki"),  # pozycja bez towaru (nie wejdzie na magazyn)
    ({"pozycja": {"towar_id": 10**9}}, "towaru"),
    ({"pozycja": {"ilosc": 1.5}}, "ilość"),          # float — niezmiennik, pkt 4
    ({"pozycja": {"ilosc": "0"}}, "ilość"),
    ({"pozycja": {"stawka_vat_kod": "0 KR"}}, "wyłączona"),
])
def test_walidacja_szkicu(klient, uzytkownik, seria, dostawca, surowiec, unikalny, zmiana, fragment):  # noqa: F811
    kontrahent_id = dostawca["id"]
    if zmiana.get("kontrahent") == "odbiorca":
        kontrahent_id = klient.post("/api/kartoteki/kontrahenci", headers=U, json=kontrahent(unikalny)).json()["id"]
    dane = zakup(seria, kontrahent_id, [pozycja(**{"towar_id": surowiec["id"], **zmiana.get("pozycja", {})})])
    r = klient.post("/api/zakupy/faktury", json=dane, headers=U)
    assert r.status_code == 422 and fragment in r.text, r.text


def test_uslugi_i_wyroby_nie_wchodza_na_fakture_zakupu(klient, uzytkownik, seria, dostawca, unikalny):  # noqa: F811
    for typ in ("usluga", "wyrob_gotowy"):
        t = klient.post("/api/kartoteki/towary", headers=U, json=towar(f"{unikalny}{typ[:2]}", typ=typ)).json()
        r = klient.post("/api/zakupy/faktury", json=zakup(seria, dostawca["id"], [pozycja(t["id"])]), headers=U)
        assert r.status_code == 422 and "towary handlowe i surowce" in r.text


def test_wylaczony_towar_nie_wejdzie_na_nowa_pozycje(klient, uzytkownik, seria, dostawca, surowiec):  # noqa: F811
    klient.put(f"/api/kartoteki/towary/{surowiec['id']}", headers=U, json={**surowiec, "aktywny": False})
    r = klient.post("/api/zakupy/faktury", json=zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]), headers=U)
    assert r.status_code == 422 and "wyłączony" in r.text


def test_seria_sprzedazy_nie_sluzy_do_zakupow(klient, uzytkownik, seria_sprzedazy, dostawca, surowiec):  # noqa: F811
    r = klient.post("/api/zakupy/faktury", headers=U,
                    json=zakup(seria_sprzedazy, dostawca["id"], [pozycja(surowiec["id"])]))
    assert r.status_code == 422 and "faktur zakupu" in r.text


def test_edycja_i_usuniecie_szkicu(klient, fabryka, uzytkownik, seria, dostawca, surowiec):  # noqa: F811
    f = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])] * 3))
    nowe = zakup(seria, dostawca["id"], [pozycja(surowiec["id"], ilosc="2", cena_netto=2500)], numer_obcy=f["numer_obcy"])
    r = klient.put(f"/api/zakupy/faktury/{f['id']}", json=nowe, headers=U)  # ten sam numer dostawcy — to ten sam szkic
    assert r.status_code == 200, r.text
    assert [(p["lp"], p["wartosc_netto"]) for p in r.json()["pozycje"]] == [(1, 5000)]
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.szkic_zmieniony"))
    assert klient.delete(f"/api/zakupy/faktury/{f['id']}", headers=U).status_code == 204
    assert klient.get(f"/api/zakupy/faktury/{f['id']}", headers=U).status_code == 404
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.szkic_usuniety"))


def test_zwykly_uzytkownik_wprowadza_zakupy(klient, zwykly, firma, seria, dostawca, surowiec):  # noqa: F811
    f = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]), naglowki=naglowek("zwykly"))
    r = klient.post(f"/api/zakupy/faktury/{f['id']}/zatwierdz", headers=naglowek("zwykly"))
    assert r.status_code == 200 and r.json()["status"] == "zatwierdzony"


# ------------------------------------------------------------------ zatwierdzenie

def test_zatwierdzenie_nadaje_numer_wlasny_i_zamraza_kopie(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec, unikalny):  # noqa: F811
    f = zatwierdz(klient, szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy="ABC/55"))["id"])
    assert f["status"] == "zatwierdzony"
    assert f["numer"] == f"FZ/{unikalny}/1/{DZIS.month:02d}/{DZIS.year}"  # własny numer
    assert f["numer_obcy"] == "ABC/55"                                       # numer dostawcy obok
    assert f["nabywca"]["nip"] and f["nabywca"]["konto"] is None            # kopia własnej firmy, bez rachunku
    assert f["dostawca_nazwa"] == dostawca["nazwa"]

    # Zmiana kartoteki NIE rusza zatwierdzonej faktury (kopia danych dostawcy).
    klient.put(f"/api/kartoteki/kontrahenci/{dostawca['id']}", headers=U, json={**dostawca, "nazwa": "Nowa nazwa"})
    assert klient.get(f"/api/zakupy/faktury/{f['id']}", headers=U).json()["dostawca_nazwa"] == dostawca["nazwa"]

    wpis = [w for w in wpisy_dziennika(fabryka, "dokument.zatwierdzony") if w.encja_id == f["id"]]
    assert len(wpis) == 1 and wpis[0].po["numer_obcy"] == "ABC/55" and wpis[0].po["suma_brutto"] == 12300


def test_braki_blokuja_zatwierdzenie_i_nie_zjadaja_numeru(klient, uzytkownik, firma, seria, dostawca, surowiec, unikalny):  # noqa: F811
    bez_numeru_obcego = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy=""))
    bez_dostawcy = szkic(klient, zakup(seria, None, [pozycja(surowiec["id"])]))
    bez_pozycji = szkic(klient, zakup(seria, dostawca["id"], []))
    bez_serii = szkic(klient, zakup(None, dostawca["id"], [pozycja(surowiec["id"])]))
    assert "Wpisz numer faktury dostawcy" in bez_numeru_obcego["braki"]
    assert "Wybierz dostawcę" in bez_dostawcy["braki"]
    for f, fragment in ((bez_numeru_obcego, "numer faktury dostawcy"), (bez_dostawcy, "dostawcę"),
                        (bez_pozycji, "pozycję"), (bez_serii, "serię")):
        r = klient.post(f"/api/zakupy/faktury/{f['id']}/zatwierdz", headers=U)
        assert r.status_code == 409 and fragment in r.json()["detail"]
    # Nieudane próby nie zużyły numerów — pierwsza poprawna faktura ma numer 1.
    ok = zatwierdz(klient, szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))["id"])
    assert ok["numer"].startswith(f"FZ/{unikalny}/1/")


def test_zatwierdzonej_nie_mozna_zmienic_usunac_ani_zatwierdzic_ponownie(klient, uzytkownik, firma, seria, dostawca, surowiec):  # noqa: F811
    f = zatwierdz(klient, szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))["id"])
    sciezka = f"/api/zakupy/faktury/{f['id']}"
    assert klient.put(sciezka, headers=U, json=zakup(seria, dostawca["id"], [pozycja(surowiec["id"])])).status_code == 409
    assert klient.delete(sciezka, headers=U).status_code == 409
    assert klient.post(f"{sciezka}/zatwierdz", headers=U).status_code == 409


def test_baza_blokuje_zmiane_zatwierdzonej_faktury_zakupu(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec):  # noqa: F811
    """Niezmiennik pilnuje także baza — nawet ręczny UPDATE z pominięciem API nie przejdzie."""
    f = zatwierdz(klient, szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))["id"])
    for sql in (
        "UPDATE dokument SET suma_netto = 1 WHERE id = :id",
        "UPDATE dokument SET numer_obcy = 'INNY' WHERE id = :id",
        "UPDATE dokument SET nabywca_nazwa = 'X' WHERE id = :id",
        "UPDATE dokument SET status = 'szkic' WHERE id = :id",
        "DELETE FROM dokument WHERE id = :id",
        "UPDATE dokument_pozycja SET cena_netto = 1 WHERE dokument_id = :id",
        "DELETE FROM dokument_pozycja WHERE dokument_id = :id",
    ):
        with pytest.raises(DBAPIError, match="szkic|nie wolno|niedozwolona"), fabryka.begin() as sesja:
            sesja.execute(text(sql), {"id": f["id"]})
    po = klient.get(f"/api/zakupy/faktury/{f['id']}", headers=U).json()
    assert (po["suma_netto"], po["status"], po["numer_obcy"]) == (10000, "zatwierdzony", f["numer_obcy"])


def test_baza_nie_pozwoli_zatwierdzic_zakupu_bez_numeru_dostawcy(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec):  # noqa: F811
    """CHECK w bazie: ręczne zatwierdzenie szkicu bez numeru obcego nie przejdzie."""
    f = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy=""))
    with pytest.raises(IntegrityError, match="zakup_numer_obcy"), fabryka.begin() as sesja:
        sesja.execute(text(
            "UPDATE dokument SET status = 'zatwierdzony', numer = 'RECZNY/1', sprzedawca = '{}'::jsonb,"
            " zatwierdzono = now() WHERE id = :id"), {"id": f["id"]})


def test_rownolegle_zatwierdzenia_daja_ciagle_numery(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec):  # noqa: F811
    ids = [szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))["id"] for _ in range(5)]
    bledy: list[Exception] = []

    def zatwierdz_w_watku(dokument_id: int) -> None:
        try:
            with fabryka.begin() as sesja:
                serwis.zatwierdz(sesja, dokument_id, uzytkownik_id=uzytkownik.id)
        except Exception as e:  # noqa: BLE001
            bledy.append(e)

    watki = [threading.Thread(target=zatwierdz_w_watku, args=(i,)) for i in ids]
    for w in watki:
        w.start()
    for w in watki:
        w.join()
    assert not bledy
    with fabryka() as sesja:
        numery = sesja.scalars(select(Dokument.numer).where(Dokument.id.in_(ids))).all()
    assert sorted(int(n.split("/")[2]) for n in numery) == [1, 2, 3, 4, 5]


def test_blad_skutku_wycofuje_cale_zatwierdzenie(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec, monkeypatch, unikalny):  # noqa: F811
    """Przyszłe PZ i zobowiązanie zapiszą się razem z fakturą albo wcale — również numer wraca do puli."""
    def zepsuty_skutek(sesja, dokument):
        raise RuntimeError("awaria modułu skutków")

    monkeypatch.setitem(serwis._SKUTKI_ZATWIERDZENIA, "faktura_zakupu", [zepsuty_skutek])
    f = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))
    with pytest.raises(RuntimeError), fabryka.begin() as sesja:
        serwis.zatwierdz(sesja, f["id"], uzytkownik_id=uzytkownik.id)
    monkeypatch.setitem(serwis._SKUTKI_ZATWIERDZENIA, "faktura_zakupu", [])
    assert klient.get(f"/api/zakupy/faktury/{f['id']}", headers=U).json()["status"] == "szkic"
    assert zatwierdz(klient, f["id"])["numer"].startswith(f"FZ/{unikalny}/1/")


# ------------------------------------------------------------------ numer faktury dostawcy

def test_ten_sam_numer_dostawcy_nie_wejdzie_dwa_razy(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec, unikalny):  # noqa: F811
    pierwsza = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy="FV 1/2026"))
    # Ten sam dostawca, ten sam numer (także inna wielkość liter i spacje) — 409, nawet dla szkicu.
    for numer in ("FV 1/2026", "fv 1/2026", "  FV 1/2026 "):
        r = klient.post("/api/zakupy/faktury", headers=U,
                        json=zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy=numer))
        assert r.status_code == 409 and "jest już w ewidencji" in r.json()["detail"]
    # Inny dostawca może mieć taki sam numer.
    inny = klient.post("/api/kartoteki/kontrahenci", headers=U, json=kontrahent(
        unikalny + "x", jest_odbiorca=False, jest_dostawca=True)).json()
    szkic(klient, zakup(seria, inny["id"], [pozycja(surowiec["id"])], numer_obcy="FV 1/2026"))
    assert pierwsza["status"] == "szkic"


def test_baza_pilnuje_unikalnosci_numeru_dostawcy(klient, fabryka, uzytkownik, seria, dostawca, surowiec):  # noqa: F811
    """Także z pominięciem API: dwa szkice tego samego dostawcy z tym samym numerem nie istnieją."""
    a = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy="DUP/1"))
    b = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy="DUP/2"))
    with pytest.raises(IntegrityError, match="uq_dokument_zakupu_numer_obcy"), fabryka.begin() as sesja:
        sesja.execute(text("UPDATE dokument SET numer_obcy = 'DUP/1' WHERE id = :id"), {"id": b["id"]})
    assert a["id"] != b["id"]


def test_anulowanie_zwalnia_numer_dostawcy_ale_nie_numer_wlasny(klient, fabryka, uzytkownik, firma, seria, dostawca, surowiec, unikalny):  # noqa: F811
    f = zatwierdz(klient, szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy="BLAD/1"))["id"])
    sciezka = f"/api/zakupy/faktury/{f['id']}/anuluj"
    assert klient.post(sciezka, headers=U, json={"przyczyna": "   "}).status_code == 409
    r = klient.post(sciezka, headers=U, json={"przyczyna": "Błędnie wprowadzona"})
    assert r.status_code == 200 and r.json()["status"] == "anulowany" and r.json()["numer"] == f["numer"]
    assert klient.post(sciezka, headers=U, json={"przyczyna": "znowu"}).status_code == 409
    # Ten sam numer dostawcy można teraz wprowadzić poprawnie, ale dostaje NASTĘPNY numer własny.
    poprawna = zatwierdz(klient, szkic(klient, zakup(
        seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy="BLAD/1"))["id"])
    assert poprawna["numer"].startswith(f"FZ/{unikalny}/2/")
    with pytest.raises(DBAPIError), fabryka.begin() as sesja:  # baza nie pozwoli „odanulować”
        sesja.execute(text("UPDATE dokument SET status = 'zatwierdzony' WHERE id = :id"), {"id": f["id"]})
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.anulowany"))


def test_szkicu_sie_nie_anuluje(klient, uzytkownik, seria, dostawca, surowiec):  # noqa: F811
    f = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))
    assert klient.post(f"/api/zakupy/faktury/{f['id']}/anuluj", headers=U, json={"przyczyna": "x"}).status_code == 409


# ------------------------------------------------------------------ rozdział od Sprzedaży, towar

def test_zakupy_i_sprzedaz_sie_nie_mieszaja(klient, uzytkownik, firma, seria, seria_sprzedazy, dostawca, surowiec, unikalny):  # noqa: F811
    z = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))
    nabywca = klient.post("/api/kartoteki/kontrahenci", headers=U, json=kontrahent(unikalny + "n")).json()
    s = klient.post("/api/sprzedaz/faktury", headers=U, json={
        "seria_id": seria_sprzedazy, "kontrahent_id": nabywca["id"], "data_wystawienia": DZIS.isoformat(),
        "data_sprzedazy": DZIS.isoformat(),
        "pozycje": [{"nazwa": "Wkładka", "jm": "szt.", "ilosc": "1", "cena_netto": 100, "stawka_vat_kod": "23"}],
    }).json()
    assert klient.get(f"/api/sprzedaz/faktury/{z['id']}", headers=U).status_code == 404
    assert klient.get(f"/api/zakupy/faktury/{s['id']}", headers=U).status_code == 404
    assert klient.post(f"/api/zakupy/faktury/{s['id']}/zatwierdz", headers=U).status_code == 404
    ids_zakupow = {w["id"] for w in klient.get("/api/zakupy/faktury?limit=200", headers=U).json()["pozycje"]}
    ids_sprzedazy = {w["id"] for w in klient.get("/api/sprzedaz/faktury?limit=200", headers=U).json()["pozycje"]}
    assert z["id"] in ids_zakupow and s["id"] not in ids_zakupow
    assert s["id"] in ids_sprzedazy and z["id"] not in ids_sprzedazy


def test_towaru_z_zatwierdzonej_faktury_zakupu_nie_mozna_zmienic_jednostki(klient, uzytkownik, firma, seria, dostawca, surowiec):  # noqa: F811
    sciezka = f"/api/kartoteki/towary/{surowiec['id']}"
    dane_towaru = {k: surowiec[k] for k in surowiec if k not in ("id", "stawka_vat_nazwa", "magazynowy")}
    f = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])]))
    assert klient.put(sciezka, headers=U, json={**dane_towaru, "jm": "g"}).status_code == 200  # tylko szkic
    zatwierdz(klient, f["id"])
    assert klient.put(sciezka, headers=U, json={**dane_towaru, "jm": "kg"}).status_code == 409
    assert klient.put(sciezka, headers=U, json={**dane_towaru, "jm": "g", "typ": "usluga"}).status_code == 409


# ------------------------------------------------------------------ lista i rejestr

def test_lista_szuka_po_numerze_dostawcy_i_sumuje_tylko_zatwierdzone(klient, uzytkownik, firma, seria, dostawca, surowiec, unikalny):  # noqa: F811
    zatwierdz(klient, szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], numer_obcy=f"SZUKAM-{unikalny}"))["id"])
    szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"], cena_netto=999999)]))
    r = klient.get(f"/api/zakupy/faktury?q={unikalny}", headers=U).json()
    assert r["razem"] == 2 and r["pozycje"][0]["status"] == "szkic"  # szkice na górze (dostawca ma unikalną nazwę)
    assert (r["suma_netto"], r["suma_brutto"]) == (10000, 12300)
    assert klient.get(f"/api/zakupy/faktury?q=SZUKAM-{unikalny}", headers=U).json()["razem"] == 1
    assert klient.get(f"/api/zakupy/faktury?q={unikalny}&status=szkic", headers=U).json()["razem"] == 1


def test_rejestr_zakupow_sumuje_vat_naliczony_po_stawkach(klient, uzytkownik, firma, seria, dostawca, surowiec):  # noqa: F811
    # Osobny, „przyszły” okres — inne testy wprowadzają faktury z dzisiejszą datą.
    dzien = date(2032, 3, 10)
    w_okresie = {"data_wystawienia": dzien.isoformat(), "data_zakupu": dzien.isoformat()}
    a = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"]), pozycja(surowiec["id"], cena_netto=500, stawka_vat_kod="8")], **w_okresie))
    b = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"], cena_netto=200, stawka_vat_kod="zw")], **w_okresie))
    anulowana = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], **w_okresie))
    szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], **w_okresie))  # szkic — poza rejestrem
    for f in (a, b, anulowana):
        zatwierdz(klient, f["id"])
    klient.post(f"/api/zakupy/faktury/{anulowana['id']}/anuluj", headers=U, json={"przyczyna": "test"})

    r = klient.get("/api/zakupy/rejestr?od=2032-03-01&do=2032-03-31", headers=U).json()
    assert [(s["kod"], s["netto"], s["vat"]) for s in r["stawki"]] == [("23", 10000, 2300), ("8", 5000, 400), ("zw", 2000, 0)]
    assert (r["netto"], r["vat"], r["brutto"]) == (17000, 2700, 19700)
    assert {d["id"] for d in r["dokumenty"]} == {a["id"], b["id"]}
    assert all(d["numer_obcy"] and d["dostawca_nazwa"] for d in r["dokumenty"])
    assert klient.get("/api/zakupy/rejestr?od=2032-03-31&do=2032-03-01", headers=U).status_code == 422
    # Rejestr sprzedaży tych samych dat jest pusty — zakupy się do niego nie wliczają.
    assert klient.get("/api/sprzedaz/rejestr?od=2032-03-01&do=2032-03-31", headers=U).json()["dokumenty"] == []
    # Wg daty zakupu: faktura wystawiona w innym miesiącu niż dostawa trafia do miesiąca dostawy.
    c = szkic(klient, zakup(seria, dostawca["id"], [pozycja(surowiec["id"])], data_wystawienia="2032-04-02", data_zakupu="2032-03-30"))
    zatwierdz(klient, c["id"])
    wg_zakupu = klient.get("/api/zakupy/rejestr?od=2032-03-01&do=2032-03-31&wg=zakupu", headers=U).json()
    assert c["id"] in {d["id"] for d in wg_zakupu["dokumenty"]}
    assert c["id"] not in {d["id"] for d in klient.get("/api/zakupy/rejestr?od=2032-03-01&do=2032-03-31", headers=U).json()["dokumenty"]}
