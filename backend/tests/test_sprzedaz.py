"""Sprzedaż: faktury VAT — wyliczenia, cykl szkic → zatwierdzenie → anulowanie i NIEZMIENNIK
(zatwierdzonej faktury nie da się zmienić ani usunąć — także z pominięciem API, numeracja bez dziur,
dokument i jego skutki w jednej transakcji, grosze jako int, dziennik zdarzeń)."""

import threading
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core import dokumenty as serwis
from app.core.numeracja import utworz_serie
from app.models import Dokument, Firma, StawkaVat
from tests.test_api_logowanie import klient, naglowek, tokeny, uzytkownik, wpisy_dziennika  # noqa: F401 — fikstury
from tests.test_kartoteki import kontrahent, towar, zwykly  # noqa: F401 — fikstury
from tests.test_ustawienia import poprawny_nip

U = naglowek("dobry")
DZIS = date.today()


@pytest.fixture
def firma(fabryka):
    """Zatwierdzenie wymaga nazwy i NIP-u sprzedawcy — uzupełniamy, jeśli inny test ich nie ustawił."""
    with fabryka.begin() as sesja:
        f = sesja.get(Firma, 1) or Firma(id=1)
        if not f.nazwa or not f.nip:
            f.nazwa, f.nip = "Pluszek Sp. z o.o.", poprawny_nip()
        sesja.add(f)


@pytest.fixture
def seria(fabryka, unikalny) -> int:
    with fabryka.begin() as sesja:
        s = utworz_serie(sesja, kod=f"FV{unikalny}", typ_dokumentu="faktura_sprzedazy", nazwa="Testowa",
                         wzorzec=f"FV/{unikalny}/{{nr}}/{{MM}}/{{RRRR}}", okres_resetu="miesiac", uzytkownik_id=None)
    return s.id


@pytest.fixture
def nabywca(klient, uzytkownik, unikalny) -> dict:  # noqa: F811
    r = klient.post("/api/kartoteki/kontrahenci", json=kontrahent(unikalny, termin_platnosci_dni=21), headers=U)
    assert r.status_code == 201, r.text
    return r.json()


def pozycja(**nadpisz) -> dict:
    return {"nazwa": "Wkładka do wanienki", "jm": "szt.", "ilosc": "1", "cena_netto": 10000, "stawka_vat_kod": "23",
            **nadpisz}


def faktura(seria_id: int | None, kontrahent_id: int | None, pozycje: list[dict] | None = None, **nadpisz) -> dict:
    return {"seria_id": seria_id, "kontrahent_id": kontrahent_id, "data_wystawienia": DZIS.isoformat(),
            "data_sprzedazy": DZIS.isoformat(), "pozycje": [pozycja()] if pozycje is None else pozycje, **nadpisz}


def szkic(klient, dane: dict, naglowki=U) -> dict:  # noqa: F811
    r = klient.post("/api/sprzedaz/faktury", json=dane, headers=naglowki)
    assert r.status_code == 201, r.text
    return r.json()


def zatwierdz(klient, faktura_id: int) -> dict:  # noqa: F811
    r = klient.post(f"/api/sprzedaz/faktury/{faktura_id}/zatwierdz", headers=U)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ wyliczenia

def test_vat_od_sumy_netto_w_stawce_a_nie_od_pozycji():
    stawki = {"23": StawkaVat(kod="23", nazwa="23", procent=23, kolejnosc=10),
              "zw": StawkaVat(kod="zw", nazwa="zw", procent=None, kolejnosc=70)}
    # 3 × 1,01 zł w 23%: od pozycji 3 × 0,23 = 0,69 zł, od sumy 3,03 × 23% = 0,6969 → 0,70 zł.
    wynik = serwis.wylicz([(Decimal("1"), 101, "23")] * 3 + [(Decimal("1.5"), 333, "zw")], stawki)
    assert wynik.wartosci == [101, 101, 101, 500]  # 1,5 × 3,33 = 4,995 → 5,00 (połówka od zera)
    assert [(s.kod, s.netto, s.vat) for s in wynik.stawki] == [("23", 303, 70), ("zw", 500, 0)]
    assert (wynik.netto, wynik.vat, wynik.brutto) == (803, 70, 873)


# ------------------------------------------------------------------ szkic

def test_sprzedaz_wymaga_logowania(klient):  # noqa: F811
    assert klient.get("/api/sprzedaz/faktury").status_code == 401
    assert klient.get(f"/api/sprzedaz/rejestr?od={DZIS}&do={DZIS}").status_code == 401


def test_szkic_liczy_sumy_i_termin_bez_numeru(klient, fabryka, uzytkownik, firma, seria, nabywca):  # noqa: F811
    dane = faktura(seria, nabywca["id"], [
        pozycja(cena_netto=101, ilosc="3"), pozycja(nazwa="Usługa", jm="usł.", cena_netto=5000, stawka_vat_kod="8"),
    ])
    f = szkic(klient, dane)
    assert f["status"] == "szkic" and f["numer"] is None
    assert (f["suma_netto"], f["suma_vat"], f["suma_brutto"]) == (5303, 70 + 400, 5303 + 470)
    assert [(s["kod"], s["netto"], s["vat"]) for s in f["stawki"]] == [("23", 303, 70), ("8", 5000, 400)]
    assert [p["lp"] for p in f["pozycje"]] == [1, 2]
    assert f["termin_platnosci"] == (DZIS + timedelta(days=21)).isoformat()  # termin kontrahenta
    assert f["nabywca_nazwa"] == nabywca["nazwa"] and f["braki"] == []
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.szkic_utworzony"))


def test_gotowka_ma_termin_rowny_dacie_wystawienia(klient, uzytkownik, seria, nabywca):  # noqa: F811
    f = szkic(klient, faktura(seria, nabywca["id"], forma_platnosci="gotowka"))
    assert f["termin_platnosci"] == DZIS.isoformat()


@pytest.mark.parametrize("zla_pozycja, kod", [
    ({"ilosc": 1.5}, 422),           # float — niezmiennik, pkt 4
    ({"ilosc": "0"}, 422),
    ({"ilosc": "1.00001"}, 422),     # więcej niż 4 miejsca po przecinku
    ({"cena_netto": -1}, 422),
    ({"stawka_vat_kod": "0 KR"}, 422),  # stawka wyłączona w Ustawieniach (stan startowy)
    ({"stawka_vat_kod": "99"}, 422),
    ({"nazwa": "   "}, 422),
])
def test_walidacja_pozycji(klient, uzytkownik, seria, nabywca, zla_pozycja, kod):  # noqa: F811
    r = klient.post("/api/sprzedaz/faktury", json=faktura(seria, nabywca["id"], [pozycja(**zla_pozycja)]), headers=U)
    assert r.status_code == kod, r.text


def test_dostawca_nie_moze_byc_nabywca(klient, uzytkownik, seria, unikalny):  # noqa: F811
    k = klient.post("/api/kartoteki/kontrahenci", headers=U,
                    json=kontrahent(unikalny, jest_odbiorca=False, jest_dostawca=True)).json()
    r = klient.post("/api/sprzedaz/faktury", json=faktura(seria, k["id"]), headers=U)
    assert r.status_code == 422 and "odbiorca" in r.json()["detail"]


def test_edycja_szkicu_podmienia_pozycje(klient, fabryka, uzytkownik, seria, nabywca):  # noqa: F811
    f = szkic(klient, faktura(seria, nabywca["id"], [pozycja(), pozycja(), pozycja()]))
    r = klient.put(f"/api/sprzedaz/faktury/{f['id']}", headers=U,
                   json=faktura(seria, nabywca["id"], [pozycja(cena_netto=2500, ilosc="2")]))
    assert r.status_code == 200, r.text
    f2 = r.json()
    assert [(p["lp"], p["wartosc_netto"]) for p in f2["pozycje"]] == [(1, 5000)]
    assert (f2["suma_netto"], f2["suma_vat"]) == (5000, 1150)
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.szkic_zmieniony"))


def test_usuniecie_szkicu(klient, fabryka, uzytkownik, seria, nabywca):  # noqa: F811
    f = szkic(klient, faktura(seria, nabywca["id"]))
    assert klient.delete(f"/api/sprzedaz/faktury/{f['id']}", headers=U).status_code == 204
    assert klient.get(f"/api/sprzedaz/faktury/{f['id']}", headers=U).status_code == 404
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.szkic_usuniety"))


def test_zwykly_uzytkownik_wystawia_faktury(klient, zwykly, firma, seria, nabywca):  # noqa: F811
    f = szkic(klient, faktura(seria, nabywca["id"]), naglowki=naglowek("zwykly"))
    r = klient.post(f"/api/sprzedaz/faktury/{f['id']}/zatwierdz", headers=naglowek("zwykly"))
    assert r.status_code == 200 and r.json()["status"] == "zatwierdzony"


# ------------------------------------------------------------------ zatwierdzenie

def test_zatwierdzenie_nadaje_numer_i_zamraza_kopie_danych(klient, fabryka, uzytkownik, firma, seria, nabywca, unikalny):  # noqa: F811
    f = zatwierdz(klient, szkic(klient, faktura(seria, nabywca["id"]))["id"])
    assert f["status"] == "zatwierdzony"
    assert f["numer"] == f"FV/{unikalny}/1/{DZIS.month:02d}/{DZIS.year}"
    assert f["sprzedawca"]["nip"] and f["nabywca_nazwa"] == nabywca["nazwa"]

    # Zmiana kartoteki NIE rusza wystawionej faktury (kopia danych).
    klient.put(f"/api/kartoteki/kontrahenci/{nabywca['id']}", headers=U, json={**nabywca, "nazwa": "Nowa nazwa"})
    assert klient.get(f"/api/sprzedaz/faktury/{f['id']}", headers=U).json()["nabywca_nazwa"] == nabywca["nazwa"]

    wpis = [w for w in wpisy_dziennika(fabryka, "dokument.zatwierdzony") if w.encja_id == f["id"]]
    assert len(wpis) == 1 and wpis[0].po["numer"] == f["numer"] and wpis[0].po["suma_brutto"] == 12300


def test_zatwierdzonej_nie_mozna_zmienic_usunac_ani_zatwierdzic_ponownie(klient, uzytkownik, firma, seria, nabywca):  # noqa: F811
    f = zatwierdz(klient, szkic(klient, faktura(seria, nabywca["id"]))["id"])
    sciezka = f"/api/sprzedaz/faktury/{f['id']}"
    assert klient.put(sciezka, headers=U, json=faktura(seria, nabywca["id"])).status_code == 409
    assert klient.delete(sciezka, headers=U).status_code == 409
    assert klient.post(f"{sciezka}/zatwierdz", headers=U).status_code == 409


def test_baza_blokuje_zmiane_zatwierdzonej_faktury(klient, fabryka, uzytkownik, firma, seria, nabywca):  # noqa: F811
    """Niezmiennik pilnuje także baza — nawet ręczny UPDATE z pominięciem API nie przejdzie."""
    f = zatwierdz(klient, szkic(klient, faktura(seria, nabywca["id"]))["id"])
    for sql in (
        "UPDATE dokument SET suma_netto = 1 WHERE id = :id",
        "UPDATE dokument SET nabywca_nazwa = 'X' WHERE id = :id",
        "UPDATE dokument SET status = 'szkic' WHERE id = :id",
        "DELETE FROM dokument WHERE id = :id",
        "UPDATE dokument_pozycja SET cena_netto = 1 WHERE dokument_id = :id",
        "DELETE FROM dokument_pozycja WHERE dokument_id = :id",
        "DELETE FROM dokument_stawka WHERE dokument_id = :id",
        "INSERT INTO dokument_pozycja (dokument_id, lp, nazwa, jm, ilosc, cena_netto, stawka_vat_kod, wartosc_netto)"
        " VALUES (:id, 99, 'x', 'szt.', 1, 1, '23', 1)",
    ):
        with pytest.raises(DBAPIError, match="szkic|nie wolno|niedozwolona"), fabryka.begin() as sesja:
            sesja.execute(text(sql), {"id": f["id"]})
    po = klient.get(f"/api/sprzedaz/faktury/{f['id']}", headers=U).json()
    assert (po["suma_netto"], po["status"], len(po["pozycje"])) == (10000, "zatwierdzony", 1)


def test_braki_blokuja_zatwierdzenie_i_nie_zjadaja_numeru(klient, uzytkownik, firma, seria, nabywca, unikalny):  # noqa: F811
    bez_nabywcy = szkic(klient, faktura(seria, None))
    bez_pozycji = szkic(klient, faktura(seria, nabywca["id"], []))
    bez_serii = szkic(klient, faktura(None, nabywca["id"]))
    assert "Wybierz nabywcę" in bez_nabywcy["braki"]
    for f, fragment in ((bez_nabywcy, "nabywcę"), (bez_pozycji, "pozycję"), (bez_serii, "serię")):
        r = klient.post(f"/api/sprzedaz/faktury/{f['id']}/zatwierdz", headers=U)
        assert r.status_code == 409 and fragment in r.json()["detail"]
    # Nieudane próby nie zużyły numerów — pierwsza poprawna faktura ma numer 1.
    ok = zatwierdz(klient, szkic(klient, faktura(seria, nabywca["id"]))["id"])
    assert ok["numer"].startswith(f"FV/{unikalny}/1/")


def test_rownolegle_zatwierdzenia_daja_ciagle_numery(klient, fabryka, uzytkownik, firma, seria, nabywca):  # noqa: F811
    ids = [szkic(klient, faktura(seria, nabywca["id"]))["id"] for _ in range(6)]
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
    assert sorted(int(n.split("/")[2]) for n in numery) == [1, 2, 3, 4, 5, 6]


def test_blad_skutku_wycofuje_cale_zatwierdzenie(klient, fabryka, uzytkownik, firma, seria, nabywca, monkeypatch, unikalny):  # noqa: F811
    """Dokument i jego skutki zapisują się razem albo wcale — również numer wraca do puli."""
    def zepsuty_skutek(sesja, dokument):
        raise RuntimeError("awaria modułu skutków")

    monkeypatch.setitem(serwis._SKUTKI_ZATWIERDZENIA, "faktura_sprzedazy", [zepsuty_skutek])
    f = szkic(klient, faktura(seria, nabywca["id"]))
    with pytest.raises(RuntimeError), fabryka.begin() as sesja:
        serwis.zatwierdz(sesja, f["id"], uzytkownik_id=uzytkownik.id)
    monkeypatch.setitem(serwis._SKUTKI_ZATWIERDZENIA, "faktura_sprzedazy", [])
    assert klient.get(f"/api/sprzedaz/faktury/{f['id']}", headers=U).json()["status"] == "szkic"
    assert zatwierdz(klient, f["id"])["numer"].startswith(f"FV/{unikalny}/1/")


# ------------------------------------------------------------------ anulowanie

def test_anulowanie_zostawia_numer_zajety(klient, fabryka, uzytkownik, firma, seria, nabywca, unikalny):  # noqa: F811
    f = zatwierdz(klient, szkic(klient, faktura(seria, nabywca["id"]))["id"])
    sciezka = f"/api/sprzedaz/faktury/{f['id']}/anuluj"
    assert klient.post(sciezka, headers=U, json={"przyczyna": "   "}).status_code == 409
    r = klient.post(sciezka, headers=U, json={"przyczyna": "Błędny nabywca"})
    assert r.status_code == 200 and r.json()["status"] == "anulowany" and r.json()["numer"] == f["numer"]
    assert klient.post(sciezka, headers=U, json={"przyczyna": "znowu"}).status_code == 409
    # Kolejna faktura dostaje NASTĘPNY numer — anulowany numer nie wraca do puli (brak duplikatów).
    nastepna = zatwierdz(klient, szkic(klient, faktura(seria, nabywca["id"]))["id"])
    assert nastepna["numer"].startswith(f"FV/{unikalny}/2/")
    # Baza nie pozwoli „odanulować”.
    with pytest.raises(DBAPIError), fabryka.begin() as sesja:
        sesja.execute(text("UPDATE dokument SET status = 'zatwierdzony' WHERE id = :id"), {"id": f["id"]})
    assert any(w.encja_id == f["id"] for w in wpisy_dziennika(fabryka, "dokument.anulowany"))


def test_szkicu_sie_nie_anuluje(klient, uzytkownik, seria, nabywca):  # noqa: F811
    f = szkic(klient, faktura(seria, nabywca["id"]))
    assert klient.post(f"/api/sprzedaz/faktury/{f['id']}/anuluj", headers=U, json={"przyczyna": "x"}).status_code == 409


# ------------------------------------------------------------------ towar na dokumentach

def test_towaru_z_zatwierdzonej_faktury_nie_mozna_zmienic_jednostki(klient, uzytkownik, firma, seria, nabywca, unikalny):  # noqa: F811
    t = klient.post("/api/kartoteki/towary", json=towar(unikalny, cena_sprzedazy_netto=1000), headers=U).json()
    sciezka = f"/api/kartoteki/towary/{t['id']}"
    dane_towaru = {k: t[k] for k in towar(unikalny) | {"jm": 0, "typ": 0, "cena_sprzedazy_netto": 0}}

    f = szkic(klient, faktura(seria, nabywca["id"], [pozycja(towar_id=t["id"], nazwa=t["nazwa"])]))
    # Towar tylko na szkicu — zmiana jm dozwolona.
    assert klient.put(sciezka, headers=U, json={**dane_towaru, "jm": "kpl."}).status_code == 200
    zatwierdz(klient, f["id"])
    assert klient.put(sciezka, headers=U, json={**dane_towaru, "jm": "op."}).status_code == 409
    assert klient.put(sciezka, headers=U, json={**dane_towaru, "jm": "kpl.", "typ": "usluga"}).status_code == 409
    # Cenę i nazwę wolno zmieniać — faktura ma własną kopię.
    assert klient.put(sciezka, headers=U, json={**dane_towaru, "jm": "kpl.", "cena_sprzedazy_netto": 2000}).status_code == 200


# ------------------------------------------------------------------ lista i rejestr

def test_lista_szuka_po_nabywcy_i_sumuje_tylko_zatwierdzone(klient, uzytkownik, firma, seria, nabywca, unikalny):  # noqa: F811
    zatwierdz(klient, szkic(klient, faktura(seria, nabywca["id"]))["id"])
    szkic(klient, faktura(seria, nabywca["id"], [pozycja(cena_netto=999999)]))
    r = klient.get(f"/api/sprzedaz/faktury?q={unikalny}", headers=U).json()
    assert r["razem"] == 2 and r["pozycje"][0]["status"] == "szkic"  # szkice na górze
    assert (r["suma_netto"], r["suma_brutto"]) == (10000, 12300)
    assert klient.get(f"/api/sprzedaz/faktury?q={unikalny}&status=szkic", headers=U).json()["razem"] == 1


def test_rejestr_sprzedazy_sumuje_po_stawkach(klient, uzytkownik, firma, seria, nabywca):  # noqa: F811
    # Osobny, „przyszły” okres — inne testy wystawiają faktury z dzisiejszą datą.
    dzien = date(2031, 3, 10)
    w_okresie = {"data_wystawienia": dzien.isoformat(), "data_sprzedazy": dzien.isoformat()}
    a = szkic(klient, faktura(seria, nabywca["id"], [pozycja(), pozycja(cena_netto=5000, stawka_vat_kod="8")], **w_okresie))
    b = szkic(klient, faktura(seria, nabywca["id"], [pozycja(cena_netto=2000, stawka_vat_kod="zw")], **w_okresie))
    anulowana = szkic(klient, faktura(seria, nabywca["id"], **w_okresie))
    szkic(klient, faktura(seria, nabywca["id"], **w_okresie))  # szkic — poza rejestrem
    for f in (a, b, anulowana):
        zatwierdz(klient, f["id"])
    klient.post(f"/api/sprzedaz/faktury/{anulowana['id']}/anuluj", headers=U, json={"przyczyna": "test"})

    r = klient.get("/api/sprzedaz/rejestr?od=2031-03-01&do=2031-03-31", headers=U).json()
    assert [(s["kod"], s["netto"], s["vat"]) for s in r["stawki"]] == [("23", 10000, 2300), ("8", 5000, 400), ("zw", 2000, 0)]
    assert (r["netto"], r["vat"], r["brutto"]) == (17000, 2700, 19700)
    assert {d["id"] for d in r["dokumenty"]} == {a["id"], b["id"]}
    assert klient.get("/api/sprzedaz/rejestr?od=2031-03-31&do=2031-03-01", headers=U).status_code == 422
