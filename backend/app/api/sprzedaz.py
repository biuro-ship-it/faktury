"""Sprzedaż: faktury VAT (szkic → zatwierdzenie → anulowanie) i rejestr sprzedaży z sumami po stawkach.

Szkic można dowolnie zmieniać i usunąć. Zatwierdzenie nadaje numer i zamraża dokument (wyzwalacz w bazie
nie pozwoli go potem zmienić). Do czasu KSeF (faza 8) faktury z aplikacji są TESTOWE — obowiązujące
wystawia Fakturownia (PLAN.md, sekcja 7, pkt 1). Moduł prowadzi każdy zalogowany użytkownik z allowlisty."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.zaleznosci import pobierz_uzytkownika
from app.core import dokumenty as serwis
from app.core.dziennik import zapisz_zdarzenie
from app.db import pobierz_sesje
from app.models import (
    Dokument, DokumentStawka, KontoBankowe, Kontrahent, SeriaNumeracji, StawkaVat, Towar, Uzytkownik,
)

router = APIRouter(prefix="/api/sprzedaz", tags=["sprzedaz"], dependencies=[Depends(pobierz_uzytkownika)])

TYP = "faktura_sprzedazy"
FormaPlatnosci = Literal["przelew", "gotowka", "karta", "mobilna"]
FiltrStatusu = Literal["wszystkie", "szkic", "zatwierdzony", "anulowany"]
MAKS_ILOSC = Decimal("9999999999")


def _422(komunikat: str) -> HTTPException:
    return HTTPException(422, komunikat)


def _wzorzec(q: str) -> str:
    ucieczka = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{ucieczka}%"


# ---------------------------------------------------------------- Schematy

class PozycjaDane(BaseModel):
    towar_id: int | None = None
    nazwa: str = Field(min_length=1, max_length=500)
    jm: str = Field(min_length=1, max_length=10)
    # Ilość jako tekst albo liczba całkowita — float odrzucamy (niezmiennik, pkt 4).
    ilosc: Decimal
    cena_netto: int = Field(ge=0, le=10**12)  # grosze za 1 j.m.
    stawka_vat_kod: str = Field(min_length=1, max_length=10)
    gtu: str | None = Field(None, max_length=6)

    @field_validator("ilosc", mode="before")
    @classmethod
    def _bez_floatow(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError("ilość podaj jako tekst, np. \"1.5\"")
        return v


class FakturaDane(BaseModel):
    seria_id: int | None = None
    kontrahent_id: int | None = None
    data_wystawienia: date
    data_sprzedazy: date
    termin_platnosci: date | None = None
    forma_platnosci: FormaPlatnosci = "przelew"
    konto_bankowe_id: int | None = None
    miejsce_wystawienia: str = Field("", max_length=100)
    wystawiajacy: str = Field("", max_length=100)
    uwagi: str = Field("", max_length=4000)
    pozycje: list[PozycjaDane] = Field(default_factory=list, max_length=500)


class PozycjaOut(PozycjaDane):
    lp: int
    wartosc_netto: int


class StawkaOut(BaseModel):
    kod: str
    nazwa: str
    netto: int
    vat: int
    brutto: int


class FakturaWiersz(BaseModel):
    id: int
    status: str
    numer: str | None
    data_wystawienia: date
    data_sprzedazy: date
    termin_platnosci: date | None
    forma_platnosci: str
    nabywca_nazwa: str
    nabywca_nip: str
    suma_netto: int
    suma_vat: int
    suma_brutto: int


class FakturaOut(FakturaWiersz):
    seria_id: int | None
    kontrahent_id: int | None
    konto_bankowe_id: int | None
    miejsce_wystawienia: str
    wystawiajacy: str
    uwagi: str
    waluta: str
    nabywca_nr_vat_ue: str
    nabywca_adres_ulica: str
    nabywca_kod_pocztowy: str
    nabywca_miejscowosc: str
    nabywca_kraj: str
    sprzedawca: dict[str, Any] | None
    pozycje: list[PozycjaOut]
    stawki: list[StawkaOut]
    utworzono: datetime
    zatwierdzono: datetime | None
    anulowano: datetime | None
    przyczyna_anulowania: str
    braki: list[str]  # dla szkicu: czego brakuje do zatwierdzenia


class ListaFaktur(BaseModel):
    pozycje: list[FakturaWiersz]
    razem: int
    # Sumy ZATWIERDZONYCH faktur spełniających filtr (szkice i anulowane się nie liczą).
    suma_netto: int
    suma_vat: int
    suma_brutto: int


class Anulowanie(BaseModel):
    przyczyna: str = Field(min_length=1, max_length=1000)


class WierszRejestru(BaseModel):
    kod: str
    nazwa: str
    netto: int
    vat: int
    brutto: int


class Rejestr(BaseModel):
    od: date
    do: date
    wg: str
    stawki: list[WierszRejestru]
    netto: int
    vat: int
    brutto: int
    dokumenty: list[FakturaWiersz]


POLA_WIERSZA = list(FakturaWiersz.model_fields)


def _wiersz(d: Dokument) -> FakturaWiersz:
    return FakturaWiersz(**{p: getattr(d, p) for p in POLA_WIERSZA})


def _nazwy_stawek(sesja: Session) -> dict[str, str]:
    return {kod: nazwa for kod, nazwa in sesja.execute(select(StawkaVat.kod, StawkaVat.nazwa))}


def _faktura_out(sesja: Session, d: Dokument) -> FakturaOut:
    nazwy = _nazwy_stawek(sesja)
    pola = {p: getattr(d, p) for p in FakturaOut.model_fields if p not in ("pozycje", "stawki", "braki")}
    return FakturaOut(
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
        raise HTTPException(404, "Nie ma takiej faktury")
    return d


# ---------------------------------------------------------------- Zapis szkicu

def przygotuj_pozycje(sesja: Session, d: Dokument, dane_pozycji: list[PozycjaDane]) -> list[serwis.PozycjaWejscie]:
    """Waliduje pozycje szkicu (ilość, stawka VAT, towar) i zamienia je na dane wejściowe serwisu.
    Wspólne dla sprzedaży i zakupów (app/api/zakupy.py)."""
    stawki = {s.kod: s for s in sesja.scalars(select(StawkaVat))}
    poprzednie_stawki = {p.stawka_vat_kod for p in d.pozycje} if d.id else set()
    pozycje: list[serwis.PozycjaWejscie] = []
    for nr, p in enumerate(dane_pozycji, start=1):
        nazwa, jm = p.nazwa.strip(), p.jm.strip()
        if not nazwa or not jm:
            raise _422(f"Pozycja {nr}: podaj nazwę i jednostkę miary")
        if p.ilosc <= 0 or p.ilosc > MAKS_ILOSC or p.ilosc != p.ilosc.quantize(Decimal("0.0001")):
            raise _422(f"Pozycja {nr}: ilość musi być dodatnia, najwyżej 4 miejsca po przecinku")
        stawka = stawki.get(p.stawka_vat_kod)
        if stawka is None:
            raise _422(f"Pozycja {nr}: nie ma stawki VAT „{p.stawka_vat_kod}”")
        if not stawka.aktywna and stawka.kod not in poprzednie_stawki:
            raise _422(f"Pozycja {nr}: stawka {stawka.kod} jest wyłączona w Ustawieniach")
        gtu = (p.gtu or "").strip().upper() or None
        if p.towar_id is not None and sesja.get(Towar, p.towar_id) is None:
            raise _422(f"Pozycja {nr}: nie ma takiego towaru")
        pozycje.append(serwis.PozycjaWejscie(p.towar_id, nazwa, jm, p.ilosc, p.cena_netto, p.stawka_vat_kod, gtu))
    return pozycje


def _sprawdz_i_zapisz(sesja: Session, d: Dokument, dane: FakturaDane) -> None:
    """Waliduje dane szkicu i przepisuje je na dokument (z kopią danych nabywcy i pozycji)."""
    if dane.data_sprzedazy.year < 2000 or dane.data_wystawienia.year < 2000:
        raise _422("Nieprawidłowa data")
    kontrahent = None
    if dane.kontrahent_id is not None:
        kontrahent = sesja.get(Kontrahent, dane.kontrahent_id)
        if kontrahent is None:
            raise _422("Nie ma takiego kontrahenta")
        if not kontrahent.jest_odbiorca:
            raise _422(f"„{kontrahent.nazwa}” nie jest oznaczony w kartotece jako odbiorca")
        if not kontrahent.aktywny and kontrahent.id != d.kontrahent_id:
            raise _422(f"Kontrahent „{kontrahent.nazwa}” jest wyłączony w kartotece")
    if dane.seria_id is not None:
        seria = sesja.get(SeriaNumeracji, dane.seria_id)
        if seria is None or seria.typ_dokumentu != TYP:
            raise _422("Wybrana seria nie służy do faktur sprzedaży")
    if dane.konto_bankowe_id is not None and sesja.get(KontoBankowe, dane.konto_bankowe_id) is None:
        raise _422("Nie ma takiego konta bankowego")
    termin = dane.termin_platnosci or serwis.domyslny_termin(
        sesja, dane.data_wystawienia, dane.forma_platnosci, kontrahent)
    if termin is not None and termin < dane.data_wystawienia:
        raise _422("Termin płatności nie może być wcześniejszy niż data wystawienia")

    pozycje = przygotuj_pozycje(sesja, d, dane.pozycje)

    d.seria_id = dane.seria_id
    d.kontrahent_id = dane.kontrahent_id
    serwis.kopiuj_nabywce(d, kontrahent)
    d.data_wystawienia = dane.data_wystawienia
    d.data_sprzedazy = dane.data_sprzedazy
    d.termin_platnosci = termin
    d.forma_platnosci = dane.forma_platnosci
    d.konto_bankowe_id = dane.konto_bankowe_id
    d.miejsce_wystawienia = dane.miejsce_wystawienia.strip()
    d.wystawiajacy = dane.wystawiajacy.strip()
    d.uwagi = dane.uwagi.strip()
    sesja.flush()
    try:
        serwis.zapisz_pozycje(sesja, d, pozycje)
    except serwis.BladDokumentu as e:
        raise _422(str(e)) from e


def _stan_szkicu(d: Dokument) -> dict[str, Any]:
    return {"kontrahent_id": d.kontrahent_id, "data_wystawienia": d.data_wystawienia.isoformat(),
            "suma_netto": d.suma_netto, "suma_brutto": d.suma_brutto, "pozycji": len(d.pozycje)}


# ---------------------------------------------------------------- Endpointy

def _filtry(zapytanie: Select, q: str, od: date | None, do: date | None) -> Select:
    if q.strip():
        wz = _wzorzec(q)
        zapytanie = zapytanie.where(or_(
            Dokument.numer.ilike(wz, escape="\\"), Dokument.nabywca_nazwa.ilike(wz, escape="\\"),
            Dokument.nabywca_nip.ilike(wz, escape="\\"),
        ))
    if od:
        zapytanie = zapytanie.where(Dokument.data_wystawienia >= od)
    if do:
        zapytanie = zapytanie.where(Dokument.data_wystawienia <= do)
    return zapytanie


@router.get("/faktury", response_model=ListaFaktur)
def lista_faktur(
    q: str = Query("", max_length=100),
    status: FiltrStatusu = "wszystkie",
    od: date | None = None,
    do: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sesja: Session = Depends(pobierz_sesje),
) -> ListaFaktur:
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
    return ListaFaktur(pozycje=[_wiersz(d) for d in wiersze], razem=razem,
                       suma_netto=int(netto), suma_vat=int(vat), suma_brutto=int(brutto))


@router.get("/faktury/{faktura_id}", response_model=FakturaOut)
def pobierz_fakture(faktura_id: int, sesja: Session = Depends(pobierz_sesje)) -> FakturaOut:
    return _faktura_out(sesja, _pobierz(sesja, faktura_id))


@router.post("/faktury", response_model=FakturaOut, status_code=201)
def dodaj_szkic(
    dane: FakturaDane, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> FakturaOut:
    d = Dokument(typ=TYP, status="szkic", data_wystawienia=dane.data_wystawienia,
                 data_sprzedazy=dane.data_sprzedazy, utworzyl_id=uzytkownik.id)
    sesja.add(d)
    sesja.flush()
    _sprawdz_i_zapisz(sesja, d, dane)
    zapisz_zdarzenie(sesja, "dokument.szkic_utworzony", uzytkownik_id=uzytkownik.id, encja="dokument",
                     encja_id=d.id, opis="Faktura sprzedaży (szkic)", po=_stan_szkicu(d))
    sesja.commit()
    return _faktura_out(sesja, d)


@router.put("/faktury/{faktura_id}", response_model=FakturaOut)
def zapisz_szkic(
    faktura_id: int, dane: FakturaDane, sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> FakturaOut:
    d = _pobierz(sesja, faktura_id, do_zmiany=True)
    if d.status != "szkic":
        raise HTTPException(409, f"Faktura {d.numer} jest zatwierdzona — zmiana tylko przez korektę")
    przed = _stan_szkicu(d)
    _sprawdz_i_zapisz(sesja, d, dane)
    d.zmieniono = datetime.now(UTC)
    zapisz_zdarzenie(sesja, "dokument.szkic_zmieniony", uzytkownik_id=uzytkownik.id, encja="dokument",
                     encja_id=d.id, przed=przed, po=_stan_szkicu(d))
    sesja.commit()
    return _faktura_out(sesja, d)


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


@router.post("/faktury/{faktura_id}/zatwierdz", response_model=FakturaOut)
def zatwierdz_fakture(
    faktura_id: int, sesja: Session = Depends(pobierz_sesje), uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> FakturaOut:
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
    return _faktura_out(sesja, d)


@router.post("/faktury/{faktura_id}/anuluj", response_model=FakturaOut)
def anuluj_fakture(
    faktura_id: int, dane: Anulowanie, sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> FakturaOut:
    _pobierz(sesja, faktura_id)
    try:
        d = serwis.anuluj(sesja, faktura_id, uzytkownik_id=uzytkownik.id, przyczyna=dane.przyczyna)
        sesja.commit()
    except serwis.BladDokumentu as e:
        sesja.rollback()
        raise HTTPException(409, str(e)) from e
    return _faktura_out(sesja, d)


@router.get("/rejestr", response_model=Rejestr)
def rejestr_sprzedazy(
    od: date, do: date, wg: Literal["wystawienia", "sprzedazy"] = "wystawienia",
    sesja: Session = Depends(pobierz_sesje),
) -> Rejestr:
    """Rejestr sprzedaży: zatwierdzone faktury z okresu (anulowane i szkice się nie liczą) i sumy po stawkach."""
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
    return Rejestr(od=od, do=do, wg=wg, stawki=stawki, netto=sum(s.netto for s in stawki),
                   vat=sum(s.vat for s in stawki), brutto=sum(s.brutto for s in stawki),
                   dokumenty=[_wiersz(d) for d in dokumenty])
