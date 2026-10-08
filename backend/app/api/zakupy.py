"""Zakupy: faktury zakupu towarów i surowców (szkic → zatwierdzenie → anulowanie) i rejestr zakupów.

Ten sam cykl i ten sam NIEZMIENNIK co w Sprzedaży (app/core/dokumenty.py, wyzwalacze w bazie): zatwierdzonej
faktury nie da się zmienić ani usunąć, numer z własnej serii dostaje dopiero zatwierdzenie, a numer faktury
dostawcy (`numer_obcy`) jest obowiązkowy i nie może się powtórzyć u tego samego dostawcy.

Na razie zatwierdzenie nie ma żadnych skutków poza numerem i rejestrem: przyjęcie na magazyn (PZ, faza 4)
i zobowiązanie (faza 3) dołożą handlery `@skutek_zatwierdzenia("faktura_zakupu")`. Cały VAT z faktury jest
traktowany jako naliczony — odliczenia częściowe (50%, brak) wejdą po ustaleniach z księgową.
Do czasu KSeF (faza 8) księgowość prowadzi Fakturownia (PLAN.md, sekcja 7, pkt 1) — to ewidencja testowa.

Kolumny dokumentu `nabywca_*` przechowują tu dane DOSTAWCY, a JSONB `sprzedawca` — kopię danych własnej firmy
(patrz app/models/dokumenty.py); na zewnątrz API używa właściwych nazw: `dostawca_*` i `nabywca`."""

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.sprzedaz import (
    Anulowanie, FiltrStatusu, FormaPlatnosci, PozycjaDane, PozycjaOut, StawkaOut, WierszRejestru, _422,
    _nazwy_stawek, _wzorzec, przygotuj_pozycje,
)
from app.auth.zaleznosci import pobierz_uzytkownika
from app.core import dokumenty as serwis
from app.core.dziennik import zapisz_zdarzenie
from app.db import pobierz_sesje
from app.models import Dokument, DokumentStawka, Kontrahent, SeriaNumeracji, StawkaVat, Towar, Uzytkownik

router = APIRouter(prefix="/api/zakupy", tags=["zakupy"], dependencies=[Depends(pobierz_uzytkownika)])

TYP = "faktura_zakupu"


# ---------------------------------------------------------------- Schematy

class ZakupDane(BaseModel):
    seria_id: int | None = None
    kontrahent_id: int | None = None  # dostawca
    numer_obcy: str = Field("", max_length=60)  # numer faktury dostawcy
    data_wystawienia: date  # data na fakturze dostawcy
    data_zakupu: date  # data dostawy towaru / wykonania usługi z faktury dostawcy
    termin_platnosci: date | None = None
    forma_platnosci: FormaPlatnosci = "przelew"
    uwagi: str = Field("", max_length=4000)
    pozycje: list[PozycjaDane] = Field(default_factory=list, max_length=500)


class ZakupWiersz(BaseModel):
    id: int
    status: str
    numer: str | None
    numer_obcy: str
    data_wystawienia: date
    data_zakupu: date
    termin_platnosci: date | None
    forma_platnosci: str
    dostawca_nazwa: str
    dostawca_nip: str
    suma_netto: int
    suma_vat: int
    suma_brutto: int


class ZakupOut(ZakupWiersz):
    seria_id: int | None
    kontrahent_id: int | None
    uwagi: str
    waluta: str
    dostawca_nr_vat_ue: str
    dostawca_adres_ulica: str
    dostawca_kod_pocztowy: str
    dostawca_miejscowosc: str
    dostawca_kraj: str
    nabywca: dict[str, Any] | None  # kopia danych własnej firmy z chwili zatwierdzenia
    pozycje: list[PozycjaOut]
    stawki: list[StawkaOut]
    utworzono: datetime
    zatwierdzono: datetime | None
    anulowano: datetime | None
    przyczyna_anulowania: str
    braki: list[str]  # dla szkicu: czego brakuje do zatwierdzenia


class ListaZakupow(BaseModel):
    pozycje: list[ZakupWiersz]
    razem: int
    # Sumy ZATWIERDZONYCH faktur spełniających filtr (szkice i anulowane się nie liczą).
    suma_netto: int
    suma_vat: int
    suma_brutto: int


class RejestrZakupow(BaseModel):
    od: date
    do: date
    wg: str
    stawki: list[WierszRejestru]
    netto: int
    vat: int  # VAT naliczony
    brutto: int
    dokumenty: list[ZakupWiersz]


# Pola dokumentu, które w API mają inną nazwę: nazwa w API → kolumna.
_INNE_NAZWY = {
    "data_zakupu": "data_sprzedazy",
    "dostawca_nazwa": "nabywca_nazwa", "dostawca_nip": "nabywca_nip", "dostawca_nr_vat_ue": "nabywca_nr_vat_ue",
    "dostawca_adres_ulica": "nabywca_adres_ulica", "dostawca_kod_pocztowy": "nabywca_kod_pocztowy",
    "dostawca_miejscowosc": "nabywca_miejscowosc", "dostawca_kraj": "nabywca_kraj", "nabywca": "sprzedawca",
}


def _pole(d: Dokument, nazwa: str) -> Any:
    return getattr(d, _INNE_NAZWY.get(nazwa, nazwa))


def _wiersz(d: Dokument) -> ZakupWiersz:
    return ZakupWiersz(**{p: _pole(d, p) for p in ZakupWiersz.model_fields})


def _zakup_out(sesja: Session, d: Dokument) -> ZakupOut:
    nazwy = _nazwy_stawek(sesja)
    pola = {p: _pole(d, p) for p in ZakupOut.model_fields if p not in ("pozycje", "stawki", "braki")}
    return ZakupOut(
        **pola,
        pozycje=[PozycjaOut(lp=p.lp, towar_id=p.towar_id, nazwa=p.nazwa, jm=p.jm, ilosc=p.ilosc,
                            cena_netto=p.cena_netto, stawka_vat_kod=p.stawka_vat_kod, gtu=p.gtu,
                            wartosc_netto=p.wartosc_netto) for p in d.pozycje],
        stawki=[StawkaOut(kod=s.stawka_vat_kod, nazwa=nazwy.get(s.stawka_vat_kod, s.stawka_vat_kod),
                          netto=s.netto, vat=s.vat, brutto=s.brutto) for s in d.stawki],
        braki=serwis.braki_do_zatwierdzenia(sesja, d) if d.status == "szkic" else [],
    )


def _pobierz(sesja: Session, faktura_id: int, *, do_zmiany: bool = False) -> Dokument:
    d = sesja.get(Dokument, faktura_id, with_for_update=do_zmiany)
    if d is None or d.typ != TYP:
        raise HTTPException(404, "Nie ma takiej faktury zakupu")
    return d


# ---------------------------------------------------------------- Zapis szkicu

def _sprawdz_i_zapisz(sesja: Session, d: Dokument, dane: ZakupDane) -> None:
    """Waliduje dane szkicu i przepisuje je na dokument (z kopią danych dostawcy i pozycji)."""
    if dane.data_zakupu.year < 2000 or dane.data_wystawienia.year < 2000:
        raise _422("Nieprawidłowa data")
    numer_obcy = dane.numer_obcy.strip()
    dostawca = None
    if dane.kontrahent_id is not None:
        dostawca = sesja.get(Kontrahent, dane.kontrahent_id)
        if dostawca is None:
            raise _422("Nie ma takiego kontrahenta")
        if not dostawca.jest_dostawca:
            raise _422(f"„{dostawca.nazwa}” nie jest oznaczony w kartotece jako dostawca")
        if not dostawca.aktywny and dostawca.id != d.kontrahent_id:
            raise _422(f"Kontrahent „{dostawca.nazwa}” jest wyłączony w kartotece")
        _sprawdz_duplikat(sesja, d, dostawca, numer_obcy)
    if dane.seria_id is not None:
        seria = sesja.get(SeriaNumeracji, dane.seria_id)
        if seria is None or seria.typ_dokumentu != TYP:
            raise _422("Wybrana seria nie służy do faktur zakupu")
    termin = dane.termin_platnosci or serwis.domyslny_termin(
        sesja, dane.data_wystawienia, dane.forma_platnosci, dostawca)
    if termin is not None and termin < dane.data_wystawienia:
        raise _422("Termin płatności nie może być wcześniejszy niż data wystawienia")

    # Faktura zakupu dotyczy towarów i surowców z kartoteki (usługi — w module Koszty). Pozycja bez towaru
    # nie mogłaby potem utworzyć przyjęcia magazynowego (PZ).
    poprzednie_towary = {p.towar_id for p in d.pozycje} if d.id else set()
    for nr, p in enumerate(dane.pozycje, start=1):
        if p.towar_id is None:
            raise _422(f"Pozycja {nr}: wybierz towar lub surowiec z kartoteki (nowy dodasz w Kartotekach)")
        towar = sesja.get(Towar, p.towar_id)
        if towar is None:
            raise _422(f"Pozycja {nr}: nie ma takiego towaru")
        if towar.typ not in serwis.MAGAZYNOWE_TYPY_TOWARU:
            raise _422(f"Pozycja {nr}: „{towar.nazwa}” to {towar.typ.replace('_', ' ')} — "
                       "faktura zakupu obejmuje towary handlowe i surowce")
        if not towar.aktywny and towar.id not in poprzednie_towary:
            raise _422(f"Pozycja {nr}: towar „{towar.nazwa}” jest wyłączony w kartotece")
    pozycje = przygotuj_pozycje(sesja, d, dane.pozycje)

    d.seria_id = dane.seria_id
    d.kontrahent_id = dane.kontrahent_id
    serwis.kopiuj_nabywce(d, dostawca)  # kolumny nabywca_* = dane dostawcy (patrz docstring modułu)
    d.numer_obcy = numer_obcy
    d.data_wystawienia = dane.data_wystawienia
    d.data_sprzedazy = dane.data_zakupu
    d.termin_platnosci = termin
    d.forma_platnosci = dane.forma_platnosci
    d.uwagi = dane.uwagi.strip()
    sesja.flush()
    try:
        serwis.zapisz_pozycje(sesja, d, pozycje)
    except serwis.BladDokumentu as e:
        raise _422(str(e)) from e


def _sprawdz_duplikat(sesja: Session, d: Dokument, dostawca: Kontrahent, numer_obcy: str) -> None:
    """Ten sam numer faktury u tego samego dostawcy (bez rozróżniania wielkości liter) — 409 z podpowiedzią,
    gdzie ta faktura już jest. Twardą gwarancję daje indeks unikalny w bazie."""
    if not numer_obcy:
        return
    istniejaca = sesja.scalar(select(Dokument).where(
        Dokument.typ == TYP, Dokument.kontrahent_id == dostawca.id, Dokument.status != "anulowany",
        func.lower(func.btrim(Dokument.numer_obcy)) == numer_obcy.lower(), Dokument.id != (d.id or -1),
    ))
    if istniejaca is not None:
        gdzie = istniejaca.numer or "szkic"
        raise HTTPException(409, f"Faktura {numer_obcy} od „{dostawca.nazwa}” jest już w ewidencji ({gdzie})")


def _stan_szkicu(d: Dokument) -> dict[str, Any]:
    return {"kontrahent_id": d.kontrahent_id, "numer_obcy": d.numer_obcy,
            "data_wystawienia": d.data_wystawienia.isoformat(), "suma_netto": d.suma_netto,
            "suma_brutto": d.suma_brutto, "pozycji": len(d.pozycje)}


# ---------------------------------------------------------------- Endpointy

def _filtry(zapytanie: Select, q: str, od: date | None, do: date | None) -> Select:
    if q.strip():
        wz = _wzorzec(q)
        zapytanie = zapytanie.where(or_(
            Dokument.numer.ilike(wz, escape="\\"), Dokument.numer_obcy.ilike(wz, escape="\\"),
            Dokument.nabywca_nazwa.ilike(wz, escape="\\"), Dokument.nabywca_nip.ilike(wz, escape="\\"),
        ))
    if od:
        zapytanie = zapytanie.where(Dokument.data_wystawienia >= od)
    if do:
        zapytanie = zapytanie.where(Dokument.data_wystawienia <= do)
    return zapytanie


@router.get("/faktury", response_model=ListaZakupow)
def lista_zakupow(
    q: str = Query("", max_length=100),
    status: FiltrStatusu = "wszystkie",
    od: date | None = None,
    do: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sesja: Session = Depends(pobierz_sesje),
) -> ListaZakupow:
    zapytanie = _filtry(select(Dokument).where(Dokument.typ == TYP), q, od, do)
    if status != "wszystkie":
        zapytanie = zapytanie.where(Dokument.status == status)
    razem = sesja.scalar(select(func.count()).select_from(zapytanie.subquery())) or 0
    podzapytanie = zapytanie.where(Dokument.status == "zatwierdzony").subquery()
    netto, vat, brutto = sesja.execute(select(
        func.coalesce(func.sum(podzapytanie.c.suma_netto), 0), func.coalesce(func.sum(podzapytanie.c.suma_vat), 0),
        func.coalesce(func.sum(podzapytanie.c.suma_brutto), 0),
    )).one()
    # Szkice na górze (czekają na zatwierdzenie), potem od najnowszych.
    wiersze = sesja.scalars(zapytanie.order_by(
        (Dokument.status == "szkic").desc(), Dokument.data_wystawienia.desc(), Dokument.id.desc(),
    ).limit(limit).offset(offset))
    return ListaZakupow(pozycje=[_wiersz(d) for d in wiersze], razem=razem,
                        suma_netto=int(netto), suma_vat=int(vat), suma_brutto=int(brutto))


@router.get("/faktury/{faktura_id}", response_model=ZakupOut)
def pobierz_zakup(faktura_id: int, sesja: Session = Depends(pobierz_sesje)) -> ZakupOut:
    return _zakup_out(sesja, _pobierz(sesja, faktura_id))


@router.post("/faktury", response_model=ZakupOut, status_code=201)
def dodaj_szkic(
    dane: ZakupDane, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> ZakupOut:
    d = Dokument(typ=TYP, status="szkic", data_wystawienia=dane.data_wystawienia,
                 data_sprzedazy=dane.data_zakupu, utworzyl_id=uzytkownik.id)
    sesja.add(d)
    sesja.flush()
    try:
        _sprawdz_i_zapisz(sesja, d, dane)
        zapisz_zdarzenie(sesja, "dokument.szkic_utworzony", uzytkownik_id=uzytkownik.id, encja="dokument",
                         encja_id=d.id, opis="Faktura zakupu (szkic)", po=_stan_szkicu(d))
        sesja.commit()
    except IntegrityError as e:  # wyścig dwóch zapisów tego samego numeru dostawcy
        sesja.rollback()
        raise HTTPException(409, "Taka faktura tego dostawcy jest już w ewidencji") from e
    return _zakup_out(sesja, d)


@router.put("/faktury/{faktura_id}", response_model=ZakupOut)
def zapisz_szkic(
    faktura_id: int, dane: ZakupDane, sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> ZakupOut:
    d = _pobierz(sesja, faktura_id, do_zmiany=True)
    if d.status != "szkic":
        raise HTTPException(409, f"Faktura {d.numer} jest zatwierdzona — zmiana tylko przez korektę")
    przed = _stan_szkicu(d)
    try:
        _sprawdz_i_zapisz(sesja, d, dane)
        d.zmieniono = datetime.now(UTC)
        zapisz_zdarzenie(sesja, "dokument.szkic_zmieniony", uzytkownik_id=uzytkownik.id, encja="dokument",
                         encja_id=d.id, przed=przed, po=_stan_szkicu(d))
        sesja.commit()
    except IntegrityError as e:
        sesja.rollback()
        raise HTTPException(409, "Taka faktura tego dostawcy jest już w ewidencji") from e
    return _zakup_out(sesja, d)


@router.delete("/faktury/{faktura_id}", status_code=204)
def usun_szkic(
    faktura_id: int, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> Response:
    d = _pobierz(sesja, faktura_id, do_zmiany=True)
    if d.status != "szkic":
        raise HTTPException(409, f"Faktury {d.numer} nie można usunąć — można ją anulować")
    zapisz_zdarzenie(sesja, "dokument.szkic_usuniety", uzytkownik_id=uzytkownik.id, encja="dokument",
                     encja_id=d.id, przed=_stan_szkicu(d))
    sesja.delete(d)
    sesja.commit()
    return Response(status_code=204)


@router.post("/faktury/{faktura_id}/zatwierdz", response_model=ZakupOut)
def zatwierdz_zakup(
    faktura_id: int, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> ZakupOut:
    _pobierz(sesja, faktura_id)
    try:
        d = serwis.zatwierdz(sesja, faktura_id, uzytkownik_id=uzytkownik.id)
        sesja.commit()
    except serwis.BladDokumentu as e:
        sesja.rollback()
        raise HTTPException(409, str(e)) from e
    except IntegrityError as e:
        sesja.rollback()
        raise HTTPException(409, "Taki numer faktury już istnieje (inna seria daje te same numery)") from e
    return _zakup_out(sesja, d)


@router.post("/faktury/{faktura_id}/anuluj", response_model=ZakupOut)
def anuluj_zakup(
    faktura_id: int, dane: Anulowanie, sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> ZakupOut:
    _pobierz(sesja, faktura_id)
    try:
        d = serwis.anuluj(sesja, faktura_id, uzytkownik_id=uzytkownik.id, przyczyna=dane.przyczyna)
        sesja.commit()
    except serwis.BladDokumentu as e:
        sesja.rollback()
        raise HTTPException(409, str(e)) from e
    return _zakup_out(sesja, d)


@router.get("/rejestr", response_model=RejestrZakupow)
def rejestr_zakupow(
    od: date, do: date, wg: str = Query("wystawienia", pattern="^(wystawienia|zakupu)$"),
    sesja: Session = Depends(pobierz_sesje),
) -> RejestrZakupow:
    """Rejestr zakupów: zatwierdzone faktury z okresu (anulowane i szkice się nie liczą) i sumy po stawkach.
    Cały VAT jest naliczony; odliczenia częściowe — po ustaleniach z księgową."""
    if do < od:
        raise _422("Data „do” jest wcześniejsza niż „od”")
    kolumna = Dokument.data_wystawienia if wg == "wystawienia" else Dokument.data_sprzedazy
    warunek = (Dokument.typ == TYP, Dokument.status == "zatwierdzony", kolumna >= od, kolumna <= do)
    sumy = sesja.execute(
        select(DokumentStawka.stawka_vat_kod, StawkaVat.nazwa, func.sum(DokumentStawka.netto),
               func.sum(DokumentStawka.vat), func.sum(DokumentStawka.brutto))
        .join(Dokument, Dokument.id == DokumentStawka.dokument_id)
        .join(StawkaVat, StawkaVat.kod == DokumentStawka.stawka_vat_kod)
        .where(*warunek)
        .group_by(DokumentStawka.stawka_vat_kod, StawkaVat.nazwa, StawkaVat.kolejnosc)
        .order_by(StawkaVat.kolejnosc)
    ).all()
    stawki = [WierszRejestru(kod=k, nazwa=n, netto=int(ne), vat=int(v), brutto=int(b)) for k, n, ne, v, b in sumy]
    dokumenty = sesja.scalars(select(Dokument).where(*warunek).order_by(kolumna, Dokument.id)).all()
    return RejestrZakupow(od=od, do=do, wg=wg, stawki=stawki, netto=sum(s.netto for s in stawki),
                          vat=sum(s.vat for s in stawki), brutto=sum(s.brutto for s in stawki),
                          dokumenty=[_wiersz(d) for d in dokumenty])
