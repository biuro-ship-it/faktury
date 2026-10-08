"""Kartoteki: kontrahenci, towary (towary handlowe, surowce, wyroby, usługi) i pracownicy.

Rekordów się nie usuwa — tylko wyłącza (`aktywny`), bo będą na nich dokumenty. Każda zmiana trafia
do dziennika zdarzeń ze stanem przed/po (tylko zmienione pola). Kartoteki prowadzi każdy zalogowany
użytkownik z allowlisty — w odróżnieniu od Ustawień nie wymagamy roli admina."""

import re
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.zaleznosci import pobierz_uzytkownika
from app.core.dziennik import zapisz_zdarzenie
from app.core.walidacja import BladWalidacji, normalizuj_nip
from app.db import pobierz_sesje
from app.models import Kontrahent, Pracownik, StawkaVat, Towar, Uzytkownik

router = APIRouter(prefix="/api/kartoteki", tags=["kartoteki"], dependencies=[Depends(pobierz_uzytkownika)])

Aktywnosc = Literal["tak", "nie", "wszystkie"]
TypKontrahenta = Literal["firma", "osoba_fizyczna"]
TypTowaru = Literal["towar_handlowy", "surowiec", "wyrob_gotowy", "usluga"]

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9._/-]{0,39}")
_GTU = re.compile(r"GTU_(0[1-9]|1[0-3])")


def _422(komunikat: str) -> HTTPException:
    return HTTPException(422, komunikat)


def _roznica(przed: dict[str, Any], po: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    klucze = [k for k in po if przed.get(k) != po[k]]
    return {k: przed.get(k) for k in klucze}, {k: po[k] for k in klucze}


def _jako_dict(obiekt: Any, pola: list[str]) -> dict[str, Any]:
    """Stan do dziennika — daty jako tekst, bo kolumna `przed`/`po` to JSONB."""
    wynik = {}
    for p in pola:
        wartosc = getattr(obiekt, p)
        wynik[p] = wartosc.isoformat() if isinstance(wartosc, date) else wartosc
    return wynik


def _oczysc(dane: BaseModel) -> dict[str, Any]:
    return {k: v.strip() if isinstance(v, str) else v for k, v in dane.model_dump().items()}


def _wzorzec(q: str) -> str:
    """Fragment do ILIKE bez znaków specjalnych LIKE (%, _) — szukamy dosłownie."""
    ucieczka = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{ucieczka}%"


def _filtr_aktywnosci(zapytanie, model, aktywnosc: Aktywnosc):  # noqa: ANN001
    if aktywnosc == "tak":
        return zapytanie.where(model.aktywny)
    if aktywnosc == "nie":
        return zapytanie.where(~model.aktywny)
    return zapytanie


def _zatwierdz(sesja: Session, komunikat: str) -> None:
    """Commit z zabezpieczeniem na wyścig: unikalność (NIP, symbol) pilnuje też baza."""
    try:
        sesja.commit()
    except IntegrityError as e:
        sesja.rollback()
        raise HTTPException(409, komunikat) from e


def _wlasciwy_email(email: str) -> None:
    if email and not _EMAIL.fullmatch(email):
        raise _422("Nieprawidłowy adres e-mail")


# ---------------------------------------------------------------- Kontrahenci

class KontrahentDane(BaseModel):
    typ: TypKontrahenta = "firma"
    nazwa: str = Field(min_length=1, max_length=250)
    nip: str = Field("", max_length=20)
    nr_vat_ue: str = Field("", max_length=20)
    regon: str = Field("", max_length=14)
    adres_ulica: str = Field("", max_length=200)
    kod_pocztowy: str = Field("", max_length=10)
    miejscowosc: str = Field("", max_length=100)
    kraj: str = Field("PL", min_length=2, max_length=2)
    email: str = Field("", max_length=254)
    telefon: str = Field("", max_length=30)
    jest_odbiorca: bool = True
    jest_dostawca: bool = False
    termin_platnosci_dni: int | None = Field(None, ge=0, le=365)
    uwagi: str = Field("", max_length=2000)
    aktywny: bool = True


class KontrahentOut(KontrahentDane):
    id: int


class ListaKontrahentow(BaseModel):
    pozycje: list[KontrahentOut]
    razem: int


POLA_KONTRAHENTA = list(KontrahentDane.model_fields)


def _kontrahent_out(k: Kontrahent) -> KontrahentOut:
    return KontrahentOut(id=k.id, **{p: getattr(k, p) for p in POLA_KONTRAHENTA})


def _sprawdz_kontrahenta(sesja: Session, nowe: dict[str, Any], *, wlasny_id: int | None) -> None:
    nowe["kraj"] = nowe["kraj"].upper()
    nowe["nr_vat_ue"] = re.sub(r"\s", "", nowe["nr_vat_ue"]).upper()
    if not nowe["nazwa"]:
        raise _422("Podaj nazwę kontrahenta")
    if not (nowe["jest_odbiorca"] or nowe["jest_dostawca"]):
        raise _422("Kontrahent musi być odbiorcą, dostawcą albo oboma")
    if nowe["nip"]:
        try:
            nowe["nip"] = normalizuj_nip(nowe["nip"])
        except BladWalidacji as e:
            raise _422(str(e)) from e
    if nowe["regon"] and not re.fullmatch(r"\d{9}|\d{14}", nowe["regon"]):
        raise _422("REGON musi mieć 9 albo 14 cyfr")
    if nowe["kraj"] == "PL" and nowe["kod_pocztowy"] and not re.fullmatch(r"\d{2}-\d{3}", nowe["kod_pocztowy"]):
        raise _422("Kod pocztowy w formacie 00-000")
    _wlasciwy_email(nowe["email"])
    if nowe["nip"]:
        zajety = select(Kontrahent.nazwa).where(Kontrahent.nip == nowe["nip"])
        if wlasny_id is not None:
            zajety = zajety.where(Kontrahent.id != wlasny_id)
        inny = sesja.scalar(zajety)
        if inny is not None:
            raise HTTPException(409, f"Kontrahent z tym NIP już istnieje: {inny}")


@router.get("/kontrahenci", response_model=ListaKontrahentow)
def lista_kontrahentow(
    q: str = Query("", max_length=100),
    aktywnosc: Aktywnosc = "tak",
    rola: Literal["wszyscy", "odbiorcy", "dostawcy"] = "wszyscy",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sesja: Session = Depends(pobierz_sesje),
) -> ListaKontrahentow:
    zapytanie = _filtr_aktywnosci(select(Kontrahent), Kontrahent, aktywnosc)
    if rola == "odbiorcy":
        zapytanie = zapytanie.where(Kontrahent.jest_odbiorca)
    elif rola == "dostawcy":
        zapytanie = zapytanie.where(Kontrahent.jest_dostawca)
    if q.strip():
        wz = _wzorzec(q)
        zapytanie = zapytanie.where(or_(
            Kontrahent.nazwa.ilike(wz, escape="\\"), Kontrahent.nip.ilike(wz, escape="\\"),
            Kontrahent.miejscowosc.ilike(wz, escape="\\"), Kontrahent.email.ilike(wz, escape="\\"),
        ))
    razem = sesja.scalar(select(func.count()).select_from(zapytanie.subquery())) or 0
    wiersze = sesja.scalars(zapytanie.order_by(func.lower(Kontrahent.nazwa), Kontrahent.id).limit(limit).offset(offset))
    return ListaKontrahentow(pozycje=[_kontrahent_out(k) for k in wiersze], razem=razem)


@router.get("/kontrahenci/{kontrahent_id}", response_model=KontrahentOut)
def pobierz_kontrahenta(kontrahent_id: int, sesja: Session = Depends(pobierz_sesje)) -> KontrahentOut:
    k = sesja.get(Kontrahent, kontrahent_id)
    if k is None:
        raise HTTPException(404, "Nie ma takiego kontrahenta")
    return _kontrahent_out(k)


@router.post("/kontrahenci", response_model=KontrahentOut, status_code=201)
def dodaj_kontrahenta(
    dane: KontrahentDane, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika)
) -> KontrahentOut:
    nowe = _oczysc(dane)
    _sprawdz_kontrahenta(sesja, nowe, wlasny_id=None)
    k = Kontrahent(**nowe)
    sesja.add(k)
    sesja.flush()
    zapisz_zdarzenie(sesja, "kontrahent.dodany", uzytkownik_id=uzytkownik.id, encja="kontrahent", encja_id=k.id,
                     opis=k.nazwa, po=_jako_dict(k, POLA_KONTRAHENTA))
    _zatwierdz(sesja, "Kontrahent z tym NIP już istnieje")
    return _kontrahent_out(k)


@router.put("/kontrahenci/{kontrahent_id}", response_model=KontrahentOut)
def zapisz_kontrahenta(
    kontrahent_id: int, dane: KontrahentDane, sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> KontrahentOut:
    k = sesja.get(Kontrahent, kontrahent_id, with_for_update=True)
    if k is None:
        raise HTTPException(404, "Nie ma takiego kontrahenta")
    nowe = _oczysc(dane)
    _sprawdz_kontrahenta(sesja, nowe, wlasny_id=k.id)
    przed = _jako_dict(k, POLA_KONTRAHENTA)
    for pole, wartosc in nowe.items():
        setattr(k, pole, wartosc)
    zmiany_przed, zmiany_po = _roznica(przed, _jako_dict(k, POLA_KONTRAHENTA))
    if zmiany_po:
        k.zmieniono = datetime.now(UTC)
        akcja = "kontrahent.zmieniony"
        if set(zmiany_po) == {"aktywny"}:
            akcja = "kontrahent.wlaczony" if k.aktywny else "kontrahent.wylaczony"
        zapisz_zdarzenie(sesja, akcja, uzytkownik_id=uzytkownik.id, encja="kontrahent", encja_id=k.id,
                         opis=k.nazwa, przed=zmiany_przed, po=zmiany_po)
    _zatwierdz(sesja, "Kontrahent z tym NIP już istnieje")
    return _kontrahent_out(k)


# ---------------------------------------------------------------- Towary

class TowarDane(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    nazwa: str = Field(min_length=1, max_length=250)
    typ: TypTowaru = "towar_handlowy"
    jm: str = Field("szt.", min_length=1, max_length=10)
    stawka_vat_kod: str = Field(min_length=1, max_length=10)
    gtu: str | None = Field(None, max_length=6)
    # Grosze za 1 jednostkę miary; NULL = brak ceny w kartotece.
    cena_sprzedazy_netto: int | None = Field(None, ge=0, le=10**12)
    ean: str = Field("", max_length=14)
    uwagi: str = Field("", max_length=2000)
    aktywny: bool = True


class TowarOut(TowarDane):
    id: int
    stawka_vat_nazwa: str
    magazynowy: bool


class ListaTowarow(BaseModel):
    pozycje: list[TowarOut]
    razem: int


POLA_TOWARU = list(TowarDane.model_fields)


def _towar_out(t: Towar, nazwa_stawki: str) -> TowarOut:
    return TowarOut(id=t.id, stawka_vat_nazwa=nazwa_stawki, magazynowy=t.typ != "usluga",
                    **{p: getattr(t, p) for p in POLA_TOWARU})


def _nazwa_stawki(sesja: Session, kod: str) -> str:
    return sesja.scalar(select(StawkaVat.nazwa).where(StawkaVat.kod == kod)) or kod


def _sprawdz_towar(sesja: Session, nowe: dict[str, Any], *, wlasny: Towar | None) -> None:
    nowe["symbol"] = nowe["symbol"].upper()
    nowe["gtu"] = (nowe["gtu"] or "").upper() or None
    if not _SYMBOL.fullmatch(nowe["symbol"]):
        raise _422("Symbol: litery bez ogonków, cyfry oraz . _ / - (maks. 40 znaków)")
    if not nowe["nazwa"]:
        raise _422("Podaj nazwę towaru")
    if not nowe["jm"]:
        raise _422("Podaj jednostkę miary")
    if nowe["gtu"] and not _GTU.fullmatch(nowe["gtu"]):
        raise _422("GTU w formacie GTU_01 … GTU_13")
    if nowe["ean"] and not re.fullmatch(r"\d{8}|\d{12,14}", nowe["ean"]):
        raise _422("EAN musi mieć 8, 12, 13 albo 14 cyfr")
    stawka = sesja.get(StawkaVat, nowe["stawka_vat_kod"])
    if stawka is None:
        raise _422("Nie ma takiej stawki VAT")
    # Wyłączona stawka nie może trafić na nowy towar, ale stary towar może ją zachować.
    if not stawka.aktywna and (wlasny is None or wlasny.stawka_vat_kod != stawka.kod):
        raise _422(f"Stawka {stawka.kod} jest wyłączona w Ustawieniach")
    zajety = select(exists().where(Towar.symbol == nowe["symbol"], Towar.id != (wlasny.id if wlasny else -1)))
    if sesja.scalar(zajety):
        raise HTTPException(409, f"Towar o symbolu {nowe['symbol']} już istnieje")


@router.get("/towary", response_model=ListaTowarow)
def lista_towarow(
    q: str = Query("", max_length=100),
    aktywnosc: Aktywnosc = "tak",
    typ: TypTowaru | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sesja: Session = Depends(pobierz_sesje),
) -> ListaTowarow:
    zapytanie = _filtr_aktywnosci(select(Towar), Towar, aktywnosc)
    if typ:
        zapytanie = zapytanie.where(Towar.typ == typ)
    if q.strip():
        wz = _wzorzec(q)
        zapytanie = zapytanie.where(or_(
            Towar.nazwa.ilike(wz, escape="\\"), Towar.symbol.ilike(wz, escape="\\"), Towar.ean.ilike(wz, escape="\\"),
        ))
    razem = sesja.scalar(select(func.count()).select_from(zapytanie.subquery())) or 0
    wiersze = sesja.scalars(zapytanie.order_by(Towar.symbol).limit(limit).offset(offset)).all()
    nazwy = {kod: nazwa for kod, nazwa in sesja.execute(select(StawkaVat.kod, StawkaVat.nazwa))}
    return ListaTowarow(pozycje=[_towar_out(t, nazwy.get(t.stawka_vat_kod, t.stawka_vat_kod)) for t in wiersze], razem=razem)


@router.get("/towary/{towar_id}", response_model=TowarOut)
def pobierz_towar(towar_id: int, sesja: Session = Depends(pobierz_sesje)) -> TowarOut:
    t = sesja.get(Towar, towar_id)
    if t is None:
        raise HTTPException(404, "Nie ma takiego towaru")
    return _towar_out(t, _nazwa_stawki(sesja, t.stawka_vat_kod))


@router.post("/towary", response_model=TowarOut, status_code=201)
def dodaj_towar(
    dane: TowarDane, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika)
) -> TowarOut:
    nowe = _oczysc(dane)
    _sprawdz_towar(sesja, nowe, wlasny=None)
    t = Towar(**nowe)
    sesja.add(t)
    sesja.flush()
    zapisz_zdarzenie(sesja, "towar.dodany", uzytkownik_id=uzytkownik.id, encja="towar", encja_id=t.id,
                     opis=t.symbol, po=_jako_dict(t, POLA_TOWARU))
    _zatwierdz(sesja, "Towar o tym symbolu już istnieje")
    return _towar_out(t, _nazwa_stawki(sesja, t.stawka_vat_kod))


@router.put("/towary/{towar_id}", response_model=TowarOut)
def zapisz_towar(
    towar_id: int, dane: TowarDane, sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> TowarOut:
    t = sesja.get(Towar, towar_id, with_for_update=True)
    if t is None:
        raise HTTPException(404, "Nie ma takiego towaru")
    nowe = _oczysc(dane)
    _sprawdz_towar(sesja, nowe, wlasny=t)
    przed = _jako_dict(t, POLA_TOWARU)
    for pole, wartosc in nowe.items():
        setattr(t, pole, wartosc)
    zmiany_przed, zmiany_po = _roznica(przed, _jako_dict(t, POLA_TOWARU))
    if zmiany_po:
        t.zmieniono = datetime.now(UTC)
        akcja = "towar.zmieniony"
        if set(zmiany_po) == {"aktywny"}:
            akcja = "towar.wlaczony" if t.aktywny else "towar.wylaczony"
        zapisz_zdarzenie(sesja, akcja, uzytkownik_id=uzytkownik.id, encja="towar", encja_id=t.id,
                         opis=t.symbol, przed=zmiany_przed, po=zmiany_po)
    _zatwierdz(sesja, "Towar o tym symbolu już istnieje")
    return _towar_out(t, _nazwa_stawki(sesja, t.stawka_vat_kod))


# ---------------------------------------------------------------- Pracownicy

class PracownikDane(BaseModel):
    imie: str = Field(min_length=1, max_length=100)
    nazwisko: str = Field(min_length=1, max_length=100)
    stanowisko: str = Field("", max_length=100)
    email: str = Field("", max_length=254)
    telefon: str = Field("", max_length=30)
    data_zatrudnienia: date | None = None
    data_zwolnienia: date | None = None
    uwagi: str = Field("", max_length=2000)
    aktywny: bool = True


class PracownikOut(PracownikDane):
    id: int


class ListaPracownikow(BaseModel):
    pozycje: list[PracownikOut]
    razem: int


POLA_PRACOWNIKA = list(PracownikDane.model_fields)


def _pracownik_out(p: Pracownik) -> PracownikOut:
    return PracownikOut(id=p.id, **{pole: getattr(p, pole) for pole in POLA_PRACOWNIKA})


def _sprawdz_pracownika(nowe: dict[str, Any]) -> None:
    if not nowe["imie"] or not nowe["nazwisko"]:
        raise _422("Podaj imię i nazwisko")
    _wlasciwy_email(nowe["email"])
    zatrudnienie, zwolnienie = nowe["data_zatrudnienia"], nowe["data_zwolnienia"]
    if zatrudnienie and zwolnienie and zwolnienie < zatrudnienie:
        raise _422("Data zwolnienia nie może być wcześniejsza niż data zatrudnienia")


@router.get("/pracownicy", response_model=ListaPracownikow)
def lista_pracownikow(
    q: str = Query("", max_length=100),
    aktywnosc: Aktywnosc = "tak",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sesja: Session = Depends(pobierz_sesje),
) -> ListaPracownikow:
    zapytanie = _filtr_aktywnosci(select(Pracownik), Pracownik, aktywnosc)
    if q.strip():
        wz = _wzorzec(q)
        zapytanie = zapytanie.where(or_(
            Pracownik.imie.ilike(wz, escape="\\"), Pracownik.nazwisko.ilike(wz, escape="\\"),
            Pracownik.stanowisko.ilike(wz, escape="\\"), Pracownik.email.ilike(wz, escape="\\"),
        ))
    razem = sesja.scalar(select(func.count()).select_from(zapytanie.subquery())) or 0
    wiersze = sesja.scalars(
        zapytanie.order_by(func.lower(Pracownik.nazwisko), func.lower(Pracownik.imie), Pracownik.id)
        .limit(limit).offset(offset)
    )
    return ListaPracownikow(pozycje=[_pracownik_out(p) for p in wiersze], razem=razem)


@router.get("/pracownicy/{pracownik_id}", response_model=PracownikOut)
def pobierz_pracownika(pracownik_id: int, sesja: Session = Depends(pobierz_sesje)) -> PracownikOut:
    p = sesja.get(Pracownik, pracownik_id)
    if p is None:
        raise HTTPException(404, "Nie ma takiego pracownika")
    return _pracownik_out(p)


@router.post("/pracownicy", response_model=PracownikOut, status_code=201)
def dodaj_pracownika(
    dane: PracownikDane, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika)
) -> PracownikOut:
    nowe = _oczysc(dane)
    _sprawdz_pracownika(nowe)
    p = Pracownik(**nowe)
    sesja.add(p)
    sesja.flush()
    zapisz_zdarzenie(sesja, "pracownik.dodany", uzytkownik_id=uzytkownik.id, encja="pracownik", encja_id=p.id,
                     opis=f"{p.imie} {p.nazwisko}", po=_jako_dict(p, POLA_PRACOWNIKA))
    sesja.commit()
    return _pracownik_out(p)


@router.put("/pracownicy/{pracownik_id}", response_model=PracownikOut)
def zapisz_pracownika(
    pracownik_id: int, dane: PracownikDane, sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> PracownikOut:
    p = sesja.get(Pracownik, pracownik_id, with_for_update=True)
    if p is None:
        raise HTTPException(404, "Nie ma takiego pracownika")
    nowe = _oczysc(dane)
    _sprawdz_pracownika(nowe)
    przed = _jako_dict(p, POLA_PRACOWNIKA)
    for pole, wartosc in nowe.items():
        setattr(p, pole, wartosc)
    zmiany_przed, zmiany_po = _roznica(przed, _jako_dict(p, POLA_PRACOWNIKA))
    if zmiany_po:
        p.zmieniono = datetime.now(UTC)
        akcja = "pracownik.zmieniony"
        if set(zmiany_po) == {"aktywny"}:
            akcja = "pracownik.wlaczony" if p.aktywny else "pracownik.wylaczony"
        zapisz_zdarzenie(sesja, akcja, uzytkownik_id=uzytkownik.id, encja="pracownik", encja_id=p.id,
                         opis=f"{p.imie} {p.nazwisko}", przed=zmiany_przed, po=zmiany_po)
    sesja.commit()
    return _pracownik_out(p)
