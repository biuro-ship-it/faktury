"""Cykl życia dokumentu: szkic → zatwierdzenie → (ewentualnie) anulowanie.

„Jeden dokument, wszystkie skutki” (PLAN.md, sekcja 2): `zatwierdz` w JEDNEJ transakcji nadaje numer,
zamraża kopię danych nabywcy i sprzedawcy, przelicza sumy, wywołuje zarejestrowane handlery skutków
(należność — faza 3, WZ — faza 4, …) i zapisuje wpis w dzienniku. Funkcje tego modułu NIE commitują —
commit robi wywołujący, więc dokument i jego skutki zapisują się razem albo wcale.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.dziennik import zapisz_zdarzenie
from app.core.numeracja import BladNumeracji, przydziel_numer
from app.core.pieniadze import Grosze, vat_od_netto, wartosc_pozycji
from app.models import (
    Dokument, DokumentPozycja, DokumentStawka, Firma, KontoBankowe, Kontrahent, SeriaNumeracji, StawkaVat,
)


TYPY_ZAKUPU = ("faktura_zakupu",)
MAGAZYNOWE_TYPY_TOWARU = ("towar_handlowy", "surowiec")  # co można kupić fakturą zakupu (usługi — moduł Koszty)


class BladDokumentu(Exception):
    """Błąd biznesowy — komunikat jest dla użytkownika."""


# ---------------------------------------------------------------- Handlery skutków

Skutek = Callable[[Session, Dokument], None]
_SKUTKI_ZATWIERDZENIA: dict[str, list[Skutek]] = {}
_SKUTKI_ANULOWANIA: dict[str, list[Skutek]] = {}


def skutek_zatwierdzenia(*typy: str) -> Callable[[Skutek], Skutek]:
    """Rejestruje funkcję wywoływaną przy zatwierdzeniu dokumentu danego typu (w tej samej transakcji).
    Kolejne moduły (rozrachunki, magazyn, KSeF) dokładają skutki bez zmiany kodu sprzedaży."""
    def rejestruj(funkcja: Skutek) -> Skutek:
        for typ in typy:
            _SKUTKI_ZATWIERDZENIA.setdefault(typ, []).append(funkcja)
        return funkcja
    return rejestruj


def skutek_anulowania(*typy: str) -> Callable[[Skutek], Skutek]:
    def rejestruj(funkcja: Skutek) -> Skutek:
        for typ in typy:
            _SKUTKI_ANULOWANIA.setdefault(typ, []).append(funkcja)
        return funkcja
    return rejestruj


# ---------------------------------------------------------------- Wyliczenia

@dataclass(frozen=True)
class PozycjaWejscie:
    towar_id: int | None
    nazwa: str
    jm: str
    ilosc: Decimal
    cena_netto: Grosze
    stawka_vat_kod: str
    gtu: str | None


@dataclass(frozen=True)
class SumaStawki:
    kod: str
    kolejnosc: int
    netto: Grosze
    vat: Grosze

    @property
    def brutto(self) -> Grosze:
        return self.netto + self.vat


@dataclass(frozen=True)
class Wyliczenie:
    wartosci: list[Grosze]  # wartość netto każdej pozycji, w kolejności pozycji
    stawki: list[SumaStawki]
    netto: Grosze
    vat: Grosze

    @property
    def brutto(self) -> Grosze:
        return self.netto + self.vat


def wylicz(pozycje: Iterable[tuple[Decimal, Grosze, str]], stawki: dict[str, StawkaVat]) -> Wyliczenie:
    """Pozycje (ilość, cena netto, kod stawki) → wartości i sumy. VAT liczony od SUMY netto w danej stawce
    (metoda zgodna z FA(3)), nie od każdej pozycji osobno. zw / np / oo — VAT 0."""
    wartosci: list[Grosze] = []
    netto_w_stawce: dict[str, Grosze] = {}
    for ilosc, cena, kod in pozycje:
        wartosc = wartosc_pozycji(ilosc, cena)
        wartosci.append(wartosc)
        netto_w_stawce[kod] = netto_w_stawce.get(kod, 0) + wartosc
    sumy = []
    for kod, netto in netto_w_stawce.items():
        stawka = stawki[kod]
        vat = vat_od_netto(netto, stawka.procent) if stawka.procent is not None else 0
        sumy.append(SumaStawki(kod=kod, kolejnosc=stawka.kolejnosc, netto=netto, vat=vat))
    sumy.sort(key=lambda s: s.kolejnosc)
    return Wyliczenie(wartosci=wartosci, stawki=sumy, netto=sum(s.netto for s in sumy), vat=sum(s.vat for s in sumy))


def _stawki_slownik(sesja: Session) -> dict[str, StawkaVat]:
    return {s.kod: s for s in sesja.scalars(select(StawkaVat))}


def zapisz_pozycje(sesja: Session, dokument: Dokument, pozycje: list[PozycjaWejscie]) -> None:
    """Podmienia pozycje szkicu i przelicza sumy. Dokument musi mieć już id (flush)."""
    if dokument.status != "szkic":
        raise BladDokumentu("Pozycje można zmieniać tylko w szkicu")
    stawki = _stawki_slownik(sesja)
    for p in pozycje:
        if p.stawka_vat_kod not in stawki:
            raise BladDokumentu(f"Nie ma stawki VAT „{p.stawka_vat_kod}”")
    wynik = wylicz(((p.ilosc, p.cena_netto, p.stawka_vat_kod) for p in pozycje), stawki)

    # Najpierw usuwamy stare wiersze jawnie — unikalność (dokument, lp) nie zniosłaby kolejności
    # „najpierw INSERT, potem DELETE”, którą stosuje SQLAlchemy przy podmianie kolekcji.
    sesja.execute(delete(DokumentPozycja).where(DokumentPozycja.dokument_id == dokument.id))
    sesja.execute(delete(DokumentStawka).where(DokumentStawka.dokument_id == dokument.id))
    sesja.expire(dokument, ["pozycje", "stawki"])
    for lp, (p, wartosc) in enumerate(zip(pozycje, wynik.wartosci, strict=True), start=1):
        sesja.add(DokumentPozycja(
            dokument_id=dokument.id, lp=lp, towar_id=p.towar_id, nazwa=p.nazwa, jm=p.jm, ilosc=p.ilosc,
            cena_netto=p.cena_netto, stawka_vat_kod=p.stawka_vat_kod, gtu=p.gtu, wartosc_netto=wartosc,
        ))
    for s in wynik.stawki:
        sesja.add(DokumentStawka(dokument_id=dokument.id, stawka_vat_kod=s.kod, kolejnosc=s.kolejnosc,
                                 netto=s.netto, vat=s.vat, brutto=s.brutto))
    dokument.suma_netto, dokument.suma_vat, dokument.suma_brutto = wynik.netto, wynik.vat, wynik.brutto
    sesja.flush()
    sesja.expire(dokument, ["pozycje", "stawki"])


def kopiuj_nabywce(dokument: Dokument, kontrahent: Kontrahent | None) -> None:
    pola = ("nazwa", "nip", "nr_vat_ue", "adres_ulica", "kod_pocztowy", "miejscowosc", "kraj")
    for pole in pola:
        domyslna = "PL" if pole == "kraj" else ""
        setattr(dokument, f"nabywca_{pole}", getattr(kontrahent, pole) if kontrahent else domyslna)


def kopia_sprzedawcy(firma: Firma, konto: KontoBankowe | None) -> dict[str, Any]:
    dane: dict[str, Any] = {pole: getattr(firma, pole) for pole in (
        "nazwa", "nip", "regon", "adres_ulica", "kod_pocztowy", "miejscowosc", "kraj", "email", "telefon", "www",
    )}
    dane["konto"] = (
        {"numer": konto.numer, "bank": konto.bank, "swift": konto.swift, "waluta": konto.waluta} if konto else None
    )
    return dane


def domyslny_termin(sesja: Session, data_wystawienia: date, forma_platnosci: str, kontrahent: Kontrahent | None) -> date | None:
    """Gotówka i karta — zapłacone przy sprzedaży, termin = data wystawienia. Przelew — termin kontrahenta,
    a gdy go nie ma, domyślny z Ustawień → Faktury."""
    if forma_platnosci in ("gotowka", "karta", "mobilna"):
        return data_wystawienia
    dni = kontrahent.termin_platnosci_dni if kontrahent and kontrahent.termin_platnosci_dni is not None else None
    if dni is None:
        firma = sesja.get(Firma, 1)
        dni = firma.termin_platnosci_dni if firma else 14
    return data_wystawienia + timedelta(days=dni)


# ---------------------------------------------------------------- Zatwierdzenie i anulowanie

def _konto_do_faktury(sesja: Session, dokument: Dokument) -> KontoBankowe | None:
    if dokument.konto_bankowe_id is not None:
        konto = sesja.get(KontoBankowe, dokument.konto_bankowe_id)
        if konto is None or not konto.aktywne:
            raise BladDokumentu("Wybrane konto bankowe jest wyłączone — wybierz inne")
        return konto
    if dokument.forma_platnosci != "przelew":
        return None
    return sesja.scalar(select(KontoBankowe).where(
        KontoBankowe.waluta == dokument.waluta, KontoBankowe.domyslne, KontoBankowe.aktywne,
    ))


def braki_do_zatwierdzenia(sesja: Session, dokument: Dokument) -> list[str]:
    """Lista powodów, dla których szkicu nie da się zatwierdzić (pusta = można)."""
    braki: list[str] = []
    firma = sesja.get(Firma, 1)
    if firma is None or not firma.nazwa.strip() or not firma.nip:
        braki.append("Uzupełnij nazwę i NIP firmy w Ustawieniach → Firma")
    seria = sesja.get(SeriaNumeracji, dokument.seria_id) if dokument.seria_id else None
    if seria is None:
        braki.append("Wybierz serię numeracji")
    elif seria.typ_dokumentu != dokument.typ:
        braki.append(f"Seria {seria.kod} nie służy do tego rodzaju dokumentu")
    elif not seria.aktywna:
        braki.append(f"Seria {seria.kod} jest wyłączona")
    zakup = dokument.typ in TYPY_ZAKUPU
    kontrahent = sesja.get(Kontrahent, dokument.kontrahent_id) if dokument.kontrahent_id else None
    if kontrahent is None:
        braki.append("Wybierz dostawcę" if zakup else "Wybierz nabywcę")
    elif not kontrahent.aktywny:
        braki.append(f"Kontrahent „{kontrahent.nazwa}” jest wyłączony w kartotece")
    if zakup and not dokument.numer_obcy.strip():
        braki.append("Wpisz numer faktury dostawcy")
    pozycje = list(dokument.pozycje)
    if not pozycje:
        braki.append("Dodaj co najmniej jedną pozycję")
    if zakup:
        for p in pozycje:
            if p.towar_id is None:
                braki.append(f"Pozycja {p.lp}: wybierz towar lub surowiec z kartoteki")
    stawki = _stawki_slownik(sesja)
    for kod in sorted({p.stawka_vat_kod for p in pozycje}):
        if not stawki[kod].aktywna:
            braki.append(f"Stawka VAT {kod} jest wyłączona w Ustawieniach")
    if dokument.termin_platnosci is not None and dokument.termin_platnosci < dokument.data_wystawienia:
        braki.append("Termin płatności nie może być wcześniejszy niż data wystawienia")
    return braki


def zatwierdz(sesja: Session, dokument_id: int, *, uzytkownik_id: int) -> Dokument:
    dokument = sesja.get(Dokument, dokument_id, with_for_update=True)
    if dokument is None:
        raise LookupError("Nie ma takiego dokumentu")
    if dokument.status != "szkic":
        raise BladDokumentu(f"Dokument {dokument.numer} jest już zatwierdzony")
    braki = braki_do_zatwierdzenia(sesja, dokument)
    if braki:
        raise BladDokumentu("Nie można zatwierdzić: " + "; ".join(braki))

    kontrahent = sesja.get(Kontrahent, dokument.kontrahent_id)
    firma = sesja.get(Firma, 1)
    seria = sesja.get(SeriaNumeracji, dokument.seria_id)
    assert kontrahent and firma and seria
    # Rachunek bankowy to rachunek SPRZEDAWCY na fakturze sprzedaży — przy zakupie nie ma czego kopiować.
    konto = None if dokument.typ in TYPY_ZAKUPU else _konto_do_faktury(sesja, dokument)

    # Sumy liczymy jeszcze raz z pozycji — zatwierdzony dokument nie może mieć „starych” sum.
    zapisz_pozycje(sesja, dokument, [
        PozycjaWejscie(p.towar_id, p.nazwa, p.jm, p.ilosc, p.cena_netto, p.stawka_vat_kod, p.gtu)
        for p in dokument.pozycje
    ])
    try:
        numer = przydziel_numer(sesja, seria.kod, dokument.data_wystawienia)
    except BladNumeracji as e:
        raise BladDokumentu(str(e)) from e

    kopiuj_nabywce(dokument, kontrahent)
    dokument.sprzedawca = kopia_sprzedawcy(firma, konto)
    dokument.konto_bankowe_id = konto.id if konto else None
    dokument.numer = numer.numer
    dokument.status = "zatwierdzony"
    dokument.zatwierdzono = datetime.now(UTC)
    dokument.zatwierdzil_id = uzytkownik_id
    sesja.flush()

    for skutek in _SKUTKI_ZATWIERDZENIA.get(dokument.typ, []):
        skutek(sesja, dokument)

    zapisz_zdarzenie(
        sesja, "dokument.zatwierdzony", uzytkownik_id=uzytkownik_id, encja="dokument", encja_id=dokument.id,
        opis=dokument.numer,
        po={"typ": dokument.typ, "numer": dokument.numer, "numer_obcy": dokument.numer_obcy,
            "kontrahent_id": dokument.kontrahent_id,
            "data_wystawienia": dokument.data_wystawienia.isoformat(), "suma_netto": dokument.suma_netto,
            "suma_vat": dokument.suma_vat, "suma_brutto": dokument.suma_brutto},
    )
    return dokument


def anuluj(sesja: Session, dokument_id: int, *, uzytkownik_id: int, przyczyna: str) -> Dokument:
    """Anulowanie zatwierdzonego dokumentu. Numer zostaje zajęty (numeracja bez dziur), dokument zostaje
    w ewidencji ze statusem „anulowany”. Skutki (należność, WZ) cofną zarejestrowane handlery."""
    przyczyna = przyczyna.strip()
    if not przyczyna:
        raise BladDokumentu("Podaj przyczynę anulowania")
    dokument = sesja.get(Dokument, dokument_id, with_for_update=True)
    if dokument is None:
        raise LookupError("Nie ma takiego dokumentu")
    if dokument.status == "szkic":
        raise BladDokumentu("Szkicu się nie anuluje — można go usunąć")
    if dokument.status == "anulowany":
        raise BladDokumentu(f"Dokument {dokument.numer} jest już anulowany")

    dokument.status = "anulowany"
    dokument.anulowano = datetime.now(UTC)
    dokument.anulowal_id = uzytkownik_id
    dokument.przyczyna_anulowania = przyczyna
    sesja.flush()
    for skutek in _SKUTKI_ANULOWANIA.get(dokument.typ, []):
        skutek(sesja, dokument)
    zapisz_zdarzenie(
        sesja, "dokument.anulowany", uzytkownik_id=uzytkownik_id, encja="dokument", encja_id=dokument.id,
        opis=dokument.numer, przed={"status": "zatwierdzony"}, po={"status": "anulowany", "przyczyna": przyczyna},
    )
    return dokument
