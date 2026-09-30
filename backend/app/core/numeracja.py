"""Numeracja dokumentów: ciągła, bez dziur i duplikatów (niezmiennik, pkt 2).

Zasada: numer przydziela się WYŁĄCZNIE wewnątrz transakcji, która zapisuje zatwierdzany
dokument. Licznik jest zwiększany instrukcją `INSERT … ON CONFLICT DO UPDATE`, która
zakłada blokadę wiersza licznika (tę samą co `SELECT … FOR UPDATE`) aż do końca transakcji:
- drugie równoległe zatwierdzenie w tej samej serii czeka na commit/rollback pierwszego,
- rollback cofa też zwiększenie licznika, więc nie zostaje dziura.
"""

import string
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.dziennik import zapisz_zdarzenie
from app.models import LicznikNumeracji, SeriaNumeracji


class BladNumeracji(Exception):
    pass


ZMIENNE_WZORCA = {"nr", "MM", "RRRR", "RR"}


@dataclass(frozen=True)
class PrzydzielonyNumer:
    numer: str
    kolejny: int
    okres: str


def waliduj_wzorzec(wzorzec: str, okres_resetu: str) -> None:
    """Odrzuca wzorce, które przy danym resecie dałyby powtarzające się numery,
    np. reset miesięczny bez miesiąca we wzorcu → „FV/1” co miesiąc."""
    try:
        pola = {nazwa for _, nazwa, _, _ in string.Formatter().parse(wzorzec) if nazwa is not None}
    except ValueError as e:
        raise BladNumeracji(f"Nieprawidłowy wzorzec „{wzorzec}”: {e}") from e
    nieznane = pola - ZMIENNE_WZORCA
    if nieznane:
        raise BladNumeracji(f"Nieznane zmienne we wzorcu: {', '.join(sorted(nieznane))}")
    if "nr" not in pola:
        raise BladNumeracji("Wzorzec musi zawierać {nr}")
    ma_rok = bool(pola & {"RRRR", "RR"})
    if okres_resetu == "miesiac" and not ("MM" in pola and ma_rok):
        raise BladNumeracji("Przy resecie miesięcznym wzorzec musi zawierać {MM} i rok")
    if okres_resetu == "rok" and not ma_rok:
        raise BladNumeracji("Przy resecie rocznym wzorzec musi zawierać rok")


def okres_dla(okres_resetu: str, data: date) -> str:
    if okres_resetu == "miesiac":
        return f"{data.year:04d}-{data.month:02d}"
    if okres_resetu == "rok":
        return f"{data.year:04d}"
    return "-"


def formatuj_numer(wzorzec: str, kolejny: int, data: date) -> str:
    return wzorzec.format(
        nr=kolejny, MM=f"{data.month:02d}", RRRR=f"{data.year:04d}", RR=f"{data.year % 100:02d}"
    )


def przydziel_numer(sesja: Session, kod_serii: str, data: date) -> PrzydzielonyNumer:
    """Zwraca kolejny numer w serii dla daty dokumentu. NIE commituje — commit robi
    transakcja zatwierdzająca dokument, razem z zapisem dokumentu i jego skutków."""
    seria = sesja.scalar(select(SeriaNumeracji).where(SeriaNumeracji.kod == kod_serii))
    if seria is None:
        raise BladNumeracji(f"Brak serii numeracji „{kod_serii}”")
    if not seria.aktywna:
        raise BladNumeracji(f"Seria numeracji „{kod_serii}” jest nieaktywna")

    okres = okres_dla(seria.okres_resetu, data)
    zapytanie = (
        insert(LicznikNumeracji)
        .values(seria_id=seria.id, okres=okres, ostatni_numer=1)
        .on_conflict_do_update(
            index_elements=[LicznikNumeracji.seria_id, LicznikNumeracji.okres],
            set_={"ostatni_numer": LicznikNumeracji.ostatni_numer + 1},
        )
        .returning(LicznikNumeracji.ostatni_numer)
    )
    kolejny = sesja.execute(zapytanie).scalar_one()
    return PrzydzielonyNumer(
        numer=formatuj_numer(seria.wzorzec, kolejny, data), kolejny=kolejny, okres=okres
    )


def utworz_serie(
    sesja: Session,
    *,
    kod: str,
    typ_dokumentu: str,
    nazwa: str,
    wzorzec: str,
    okres_resetu: str,
    uzytkownik_id: int | None,
) -> SeriaNumeracji:
    waliduj_wzorzec(wzorzec, okres_resetu)
    seria = SeriaNumeracji(
        kod=kod, typ_dokumentu=typ_dokumentu, nazwa=nazwa, wzorzec=wzorzec, okres_resetu=okres_resetu
    )
    sesja.add(seria)
    sesja.flush()
    zapisz_zdarzenie(
        sesja,
        "seria_numeracji.utworzona",
        uzytkownik_id=uzytkownik_id,
        encja="seria_numeracji",
        encja_id=seria.id,
        po={"kod": kod, "wzorzec": wzorzec, "okres_resetu": okres_resetu},
    )
    return seria
