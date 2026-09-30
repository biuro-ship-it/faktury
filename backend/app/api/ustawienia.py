"""Ustawienia: dane firmy, konta bankowe, stawki VAT, serie numeracji. Zmiany tylko dla admina,
każda z wpisem w dzienniku zdarzeń (stan przed/po)."""

import re
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.zaleznosci import pobierz_uzytkownika, wymagaj_admina
from app.core import biala_lista
from app.core.dziennik import zapisz_zdarzenie
from app.core.numeracja import BladNumeracji, formatuj_numer, utworz_serie, waliduj_wzorzec
from app.core.walidacja import BladWalidacji, formatuj_iban, normalizuj_iban, normalizuj_nip
from app.db import pobierz_sesje
from app.models import Firma, KontoBankowe, LicznikNumeracji, SeriaNumeracji, StawkaVat, Uzytkownik

router = APIRouter(prefix="/api/ustawienia", tags=["ustawienia"], dependencies=[Depends(pobierz_uzytkownika)])

TypDokumentu = Literal[
    "faktura_sprzedazy", "korekta_sprzedazy", "proforma", "faktura_zakupu", "faktura_kosztowa",
    "kp", "kw", "bo", "pz", "wz", "rw", "pw", "mm", "inwentaryzacja", "zlecenie_produkcyjne",
]


def _roznica(przed: dict[str, Any], po: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    klucze = [k for k in po if przed.get(k) != po[k]]
    return {k: przed.get(k) for k in klucze}, {k: po[k] for k in klucze}


def _422(komunikat: str) -> HTTPException:
    return HTTPException(422, komunikat)


# ---------------------------------------------------------------- Firma

class FirmaDane(BaseModel):
    nazwa: str = Field("", max_length=250)
    nazwa_skrocona: str = Field("", max_length=100)
    nip: str = Field("", max_length=20)
    regon: str = Field("", max_length=14)
    adres_ulica: str = Field("", max_length=200)
    kod_pocztowy: str = Field("", max_length=10)
    miejscowosc: str = Field("", max_length=100)
    kraj: str = Field("PL", min_length=2, max_length=2)
    email: str = Field("", max_length=254)
    telefon: str = Field("", max_length=30)
    www: str = Field("", max_length=200)
    miejsce_wystawienia: str = Field("", max_length=100)
    termin_platnosci_dni: int = Field(14, ge=0, le=365)
    forma_platnosci: Literal["przelew", "gotowka", "karta", "mobilna"] = "przelew"
    wystawiajacy: str = Field("", max_length=100)
    uwagi_na_fakturze: str = Field("", max_length=2000)


POLA_FIRMY = list(FirmaDane.model_fields)


def _firma_dict(f: Firma) -> dict[str, Any]:
    return {k: getattr(f, k) for k in POLA_FIRMY}


@router.get("/firma", response_model=FirmaDane)
def pobierz_firme(sesja: Session = Depends(pobierz_sesje)) -> FirmaDane:
    firma = sesja.get(Firma, 1)
    return FirmaDane(**_firma_dict(firma)) if firma else FirmaDane()


@router.put("/firma", response_model=FirmaDane)
def zapisz_firme(
    dane: FirmaDane,
    sesja: Session = Depends(pobierz_sesje),
    admin: Uzytkownik = Depends(wymagaj_admina),
) -> FirmaDane:
    nowe = {k: v.strip() if isinstance(v, str) else v for k, v in dane.model_dump().items()}
    nowe["kraj"] = nowe["kraj"].upper()
    try:
        if nowe["nip"]:
            nowe["nip"] = normalizuj_nip(nowe["nip"])
    except BladWalidacji as e:
        raise _422(str(e)) from e
    if nowe["regon"] and not re.fullmatch(r"\d{9}|\d{14}", nowe["regon"]):
        raise _422("REGON musi mieć 9 albo 14 cyfr")
    if nowe["kraj"] == "PL" and nowe["kod_pocztowy"] and not re.fullmatch(r"\d{2}-\d{3}", nowe["kod_pocztowy"]):
        raise _422("Kod pocztowy w formacie 00-000")
    if nowe["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", nowe["email"]):
        raise _422("Nieprawidłowy adres e-mail")

    firma = sesja.get(Firma, 1, with_for_update=True)
    przed = _firma_dict(firma) if firma else {}
    if firma is None:
        firma = Firma(id=1)
        sesja.add(firma)
    for k, v in nowe.items():
        setattr(firma, k, v)
    zmiany_przed, zmiany_po = _roznica(przed, nowe)
    if zmiany_po:
        firma.zmieniono = datetime.now(UTC)
        zapisz_zdarzenie(sesja, "firma.zmieniona", uzytkownik_id=admin.id, encja="firma", encja_id=1,
                         przed=zmiany_przed, po=zmiany_po)
    sesja.commit()
    return FirmaDane(**_firma_dict(firma))


class PodmiotZBialejListy(BaseModel):
    nazwa: str
    nip: str
    regon: str
    status_vat: str
    adres_ulica: str
    kod_pocztowy: str
    miejscowosc: str
    konta: list[str]


@router.get("/biala-lista/{nip}", response_model=PodmiotZBialejListy)
def z_bialej_listy(nip: str) -> PodmiotZBialejListy:
    try:
        dane = biala_lista.pobierz(normalizuj_nip(nip))
    except BladWalidacji as e:
        raise _422(str(e)) from e
    except biala_lista.BladBialejListy as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    return PodmiotZBialejListy(**{**dane.__dict__, "konta": [formatuj_iban("PL" + k) for k in dane.konta]})


# ---------------------------------------------------------------- Konta bankowe

class KontoOut(BaseModel):
    id: int
    nazwa: str
    numer: str
    numer_sformatowany: str
    bank: str
    swift: str
    waluta: str
    domyslne: bool
    aktywne: bool


class NoweKonto(BaseModel):
    nazwa: str = Field(min_length=1, max_length=100)
    numer: str = Field(min_length=1, max_length=50)
    bank: str = Field("", max_length=100)
    swift: str = Field("", max_length=11)
    waluta: str = Field("PLN", pattern=r"^[A-Za-z]{3}$")
    domyslne: bool = False


class ZmianaKonta(BaseModel):
    nazwa: str | None = Field(None, min_length=1, max_length=100)
    bank: str | None = Field(None, max_length=100)
    swift: str | None = Field(None, max_length=11)
    domyslne: Literal[True] | None = None
    aktywne: bool | None = None


def _konto_out(k: KontoBankowe) -> KontoOut:
    return KontoOut(id=k.id, nazwa=k.nazwa, numer=k.numer, numer_sformatowany=formatuj_iban(k.numer),
                    bank=k.bank, swift=k.swift, waluta=k.waluta, domyslne=k.domyslne, aktywne=k.aktywne)


def _konto_dict(k: KontoBankowe) -> dict[str, Any]:
    return {p: getattr(k, p) for p in ("nazwa", "numer", "bank", "swift", "waluta", "domyslne", "aktywne")}


def _ustaw_domyslne(sesja: Session, konto: KontoBankowe) -> None:
    sesja.execute(
        update(KontoBankowe)
        .where(KontoBankowe.waluta == konto.waluta, KontoBankowe.domyslne, KontoBankowe.id != konto.id)
        .values(domyslne=False)
    )
    sesja.flush()
    konto.domyslne = True


@router.get("/konta", response_model=list[KontoOut])
def lista_kont(sesja: Session = Depends(pobierz_sesje)) -> list[KontoOut]:
    konta = sesja.scalars(select(KontoBankowe).order_by(KontoBankowe.aktywne.desc(), KontoBankowe.id))
    return [_konto_out(k) for k in konta]


@router.post("/konta", response_model=KontoOut, status_code=201)
def dodaj_konto(
    dane: NoweKonto, sesja: Session = Depends(pobierz_sesje), admin: Uzytkownik = Depends(wymagaj_admina)
) -> KontoOut:
    try:
        numer = normalizuj_iban(dane.numer)
    except BladWalidacji as e:
        raise _422(str(e)) from e
    if sesja.scalar(select(exists().where(KontoBankowe.numer == numer))):
        raise HTTPException(409, "To konto jest już na liście")
    waluta = dane.waluta.upper()
    pierwsze_w_walucie = not sesja.scalar(
        select(exists().where(KontoBankowe.waluta == waluta, KontoBankowe.aktywne))
    )
    konto = KontoBankowe(nazwa=dane.nazwa.strip(), numer=numer, bank=dane.bank.strip(),
                         swift=dane.swift.strip().upper(), waluta=waluta)
    sesja.add(konto)
    sesja.flush()
    if dane.domyslne or pierwsze_w_walucie:
        _ustaw_domyslne(sesja, konto)
    zapisz_zdarzenie(sesja, "konto_bankowe.dodane", uzytkownik_id=admin.id, encja="konto_bankowe",
                     encja_id=konto.id, po=_konto_dict(konto))
    sesja.commit()
    return _konto_out(konto)


@router.patch("/konta/{konto_id}", response_model=KontoOut)
def zmien_konto(
    konto_id: int, dane: ZmianaKonta, sesja: Session = Depends(pobierz_sesje),
    admin: Uzytkownik = Depends(wymagaj_admina),
) -> KontoOut:
    konto = sesja.get(KontoBankowe, konto_id, with_for_update=True)
    if konto is None:
        raise HTTPException(404, "Nie ma takiego konta")
    przed = _konto_dict(konto)
    for pole in ("nazwa", "bank", "swift"):
        wartosc = getattr(dane, pole)
        if wartosc is not None:
            setattr(konto, pole, wartosc.strip().upper() if pole == "swift" else wartosc.strip())
    if dane.aktywne is not None:
        konto.aktywne = dane.aktywne
        if not dane.aktywne:
            konto.domyslne = False
    if dane.domyslne:
        if not konto.aktywne:
            raise _422("Nieaktywne konto nie może być domyślne")
        _ustaw_domyslne(sesja, konto)
    zmiany_przed, zmiany_po = _roznica(przed, _konto_dict(konto))
    if zmiany_po:
        zapisz_zdarzenie(sesja, "konto_bankowe.zmienione", uzytkownik_id=admin.id, encja="konto_bankowe",
                         encja_id=konto.id, przed=zmiany_przed, po=zmiany_po)
    sesja.commit()
    return _konto_out(konto)


# ---------------------------------------------------------------- Stawki VAT

class StawkaOut(BaseModel):
    kod: str
    nazwa: str
    procent: int | None
    aktywna: bool
    domyslna: bool


class ZmianaStawki(BaseModel):
    aktywna: bool | None = None
    domyslna: Literal[True] | None = None


def _stawka_out(s: StawkaVat) -> StawkaOut:
    return StawkaOut(kod=s.kod, nazwa=s.nazwa, procent=s.procent, aktywna=s.aktywna, domyslna=s.domyslna)


@router.get("/stawki-vat", response_model=list[StawkaOut])
def lista_stawek(sesja: Session = Depends(pobierz_sesje)) -> list[StawkaOut]:
    return [_stawka_out(s) for s in sesja.scalars(select(StawkaVat).order_by(StawkaVat.kolejnosc))]


@router.patch("/stawki-vat/{kod}", response_model=StawkaOut)
def zmien_stawke(
    kod: str, dane: ZmianaStawki, sesja: Session = Depends(pobierz_sesje),
    admin: Uzytkownik = Depends(wymagaj_admina),
) -> StawkaOut:
    stawka = sesja.get(StawkaVat, kod, with_for_update=True)
    if stawka is None:
        raise HTTPException(404, "Nie ma takiej stawki")
    przed = {"aktywna": stawka.aktywna, "domyslna": stawka.domyslna}
    if dane.aktywna is False and stawka.domyslna:
        raise _422("Nie można wyłączyć stawki domyślnej — najpierw ustaw inną jako domyślną")
    if dane.aktywna is not None:
        stawka.aktywna = dane.aktywna
    if dane.domyslna:
        if not stawka.aktywna:
            raise _422("Domyślna może być tylko aktywna stawka")
        sesja.execute(update(StawkaVat).where(StawkaVat.domyslna, StawkaVat.kod != kod).values(domyslna=False))
        sesja.flush()
        stawka.domyslna = True
    zmiany_przed, zmiany_po = _roznica(przed, {"aktywna": stawka.aktywna, "domyslna": stawka.domyslna})
    if zmiany_po:
        zapisz_zdarzenie(sesja, "stawka_vat.zmieniona", uzytkownik_id=admin.id, encja="stawka_vat",
                         opis=kod, przed=zmiany_przed, po=zmiany_po)
    sesja.commit()
    return _stawka_out(stawka)


# ---------------------------------------------------------------- Serie numeracji

class SeriaOut(BaseModel):
    id: int
    kod: str
    typ_dokumentu: str
    nazwa: str
    wzorzec: str
    okres_resetu: str
    aktywna: bool
    przyklad: str
    uzyta: bool


class NowaSeria(BaseModel):
    kod: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    typ_dokumentu: TypDokumentu
    nazwa: str = Field(min_length=1, max_length=100)
    wzorzec: str = Field(min_length=1, max_length=60)
    okres_resetu: Literal["miesiac", "rok", "brak"]


class ZmianaSerii(BaseModel):
    nazwa: str | None = Field(None, min_length=1, max_length=100)
    aktywna: bool | None = None


class PodgladWzorca(BaseModel):
    wzorzec: str = Field(max_length=60)
    okres_resetu: Literal["miesiac", "rok", "brak"]


def _seria_out(sesja: Session, s: SeriaNumeracji) -> SeriaOut:
    uzyta = sesja.scalar(select(exists().where(LicznikNumeracji.seria_id == s.id))) or False
    return SeriaOut(id=s.id, kod=s.kod, typ_dokumentu=s.typ_dokumentu, nazwa=s.nazwa, wzorzec=s.wzorzec,
                    okres_resetu=s.okres_resetu, aktywna=s.aktywna, uzyta=uzyta,
                    przyklad=formatuj_numer(s.wzorzec, 1, date.today()))


@router.get("/serie", response_model=list[SeriaOut])
def lista_serii(sesja: Session = Depends(pobierz_sesje)) -> list[SeriaOut]:
    serie = sesja.scalars(select(SeriaNumeracji).order_by(SeriaNumeracji.typ_dokumentu, SeriaNumeracji.kod)).all()
    return [_seria_out(sesja, s) for s in serie]


@router.post("/serie/podglad")
def podglad_wzorca(dane: PodgladWzorca) -> dict[str, str]:
    try:
        waliduj_wzorzec(dane.wzorzec, dane.okres_resetu)
    except BladNumeracji as e:
        raise _422(str(e)) from e
    return {"przyklad": formatuj_numer(dane.wzorzec, 1, date.today())}


@router.post("/serie", response_model=SeriaOut, status_code=201)
def dodaj_serie(
    dane: NowaSeria, sesja: Session = Depends(pobierz_sesje), admin: Uzytkownik = Depends(wymagaj_admina)
) -> SeriaOut:
    kod = dane.kod.upper()
    if sesja.scalar(select(exists().where(SeriaNumeracji.kod == kod))):
        raise HTTPException(409, f"Seria o kodzie {kod} już istnieje")
    try:
        seria = utworz_serie(sesja, kod=kod, typ_dokumentu=dane.typ_dokumentu, nazwa=dane.nazwa.strip(),
                             wzorzec=dane.wzorzec, okres_resetu=dane.okres_resetu, uzytkownik_id=admin.id)
    except BladNumeracji as e:
        raise _422(str(e)) from e
    try:
        sesja.commit()
    except IntegrityError as e:
        raise HTTPException(409, f"Seria o kodzie {kod} już istnieje") from e
    return _seria_out(sesja, seria)


@router.patch("/serie/{seria_id}", response_model=SeriaOut)
def zmien_serie(
    seria_id: int, dane: ZmianaSerii, sesja: Session = Depends(pobierz_sesje),
    admin: Uzytkownik = Depends(wymagaj_admina),
) -> SeriaOut:
    # Wzorca i resetu nie zmieniamy — numery już nadane muszą pozostać spójne. Nowy wzorzec = nowa seria.
    seria = sesja.get(SeriaNumeracji, seria_id, with_for_update=True)
    if seria is None:
        raise HTTPException(404, "Nie ma takiej serii")
    przed = {"nazwa": seria.nazwa, "aktywna": seria.aktywna}
    if dane.nazwa is not None:
        seria.nazwa = dane.nazwa.strip()
    if dane.aktywna is not None:
        seria.aktywna = dane.aktywna
    zmiany_przed, zmiany_po = _roznica(przed, {"nazwa": seria.nazwa, "aktywna": seria.aktywna})
    if zmiany_po:
        zapisz_zdarzenie(sesja, "seria_numeracji.zmieniona", uzytkownik_id=admin.id, encja="seria_numeracji",
                         encja_id=seria.id, przed=zmiany_przed, po=zmiany_po)
    sesja.commit()
    return _seria_out(sesja, seria)
