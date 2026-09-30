"""Niezmiennik pkt 2: numeracja w serii ciągła, bez dziur i duplikatów — także przy
równoległych zatwierdzeniach i wycofanych transakcjach."""

import threading
import time
from datetime import date

import pytest
from sqlalchemy import select

from app.core.numeracja import BladNumeracji, przydziel_numer, utworz_serie, waliduj_wzorzec
from app.models import SeriaNumeracji

WRZESIEN = date(2026, 9, 15)
PAZDZIERNIK = date(2026, 10, 1)


@pytest.fixture
def nowa_seria(fabryka, unikalny):
    def _utworz(wzorzec: str = "FV/{nr}/{MM}/{RRRR}", okres_resetu: str = "miesiac") -> str:
        kod = f"T{unikalny}"
        with fabryka.begin() as sesja:
            utworz_serie(
                sesja, kod=kod, typ_dokumentu="faktura_sprzedazy", nazwa="test",
                wzorzec=wzorzec, okres_resetu=okres_resetu, uzytkownik_id=None,
            )
        return kod

    return _utworz


def zatwierdz(fabryka, kod: str, data: date = WRZESIEN) -> str:
    with fabryka.begin() as sesja:
        return przydziel_numer(sesja, kod, data).numer


def test_kolejne_numery_w_serii(fabryka, nowa_seria):
    kod = nowa_seria()
    assert [zatwierdz(fabryka, kod) for _ in range(3)] == [
        "FV/1/09/2026", "FV/2/09/2026", "FV/3/09/2026",
    ]


def test_reset_miesieczny_zaczyna_od_1_w_nowym_miesiacu(fabryka, nowa_seria):
    kod = nowa_seria()
    zatwierdz(fabryka, kod, WRZESIEN)
    zatwierdz(fabryka, kod, WRZESIEN)
    assert zatwierdz(fabryka, kod, PAZDZIERNIK) == "FV/1/10/2026"
    assert zatwierdz(fabryka, kod, WRZESIEN) == "FV/3/09/2026"


def test_reset_roczny_i_dopelnienie_zerami(fabryka, nowa_seria):
    kod = nowa_seria("KP/{nr:04d}/{RR}", "rok")
    assert zatwierdz(fabryka, kod, WRZESIEN) == "KP/0001/26"
    assert zatwierdz(fabryka, kod, PAZDZIERNIK) == "KP/0002/26"
    assert zatwierdz(fabryka, kod, date(2027, 1, 2)) == "KP/0001/27"


def test_bez_resetu(fabryka, nowa_seria):
    kod = nowa_seria("ZP/{nr}", "brak")
    zatwierdz(fabryka, kod, WRZESIEN)
    assert zatwierdz(fabryka, kod, date(2030, 1, 1)) == "ZP/2"


@pytest.mark.parametrize(
    ("wzorzec", "okres"),
    [
        ("FV/{MM}/{RRRR}", "miesiac"),       # brak {nr}
        ("FV/{nr}/{RRRR}", "miesiac"),       # reset miesięczny bez miesiąca → duplikaty
        ("FV/{nr}/{MM}", "miesiac"),         # reset miesięczny bez roku → duplikaty co rok
        ("FV/{nr}", "rok"),                  # reset roczny bez roku
        ("FV/{nr}/{DZIEN}", "brak"),         # nieznana zmienna
        ("FV/{nr", "brak"),                  # błędna składnia
    ],
)
def test_wzorzec_grozacy_duplikatami_jest_odrzucany(wzorzec, okres):
    with pytest.raises(BladNumeracji):
        waliduj_wzorzec(wzorzec, okres)


def test_nieznana_i_nieaktywna_seria(fabryka, nowa_seria):
    with fabryka.begin() as sesja, pytest.raises(BladNumeracji):
        przydziel_numer(sesja, "NIE-MA-TAKIEJ", WRZESIEN)

    kod = nowa_seria()
    with fabryka.begin() as sesja:
        sesja.scalar(select(SeriaNumeracji).where(SeriaNumeracji.kod == kod)).aktywna = False
    with fabryka.begin() as sesja, pytest.raises(BladNumeracji):
        przydziel_numer(sesja, kod, WRZESIEN)


def test_wycofana_transakcja_nie_zostawia_dziury(fabryka, nowa_seria):
    kod = nowa_seria()
    zatwierdz(fabryka, kod)
    with fabryka() as sesja:
        with sesja.begin():
            assert przydziel_numer(sesja, kod, WRZESIEN).kolejny == 2
            sesja.rollback()  # np. błąd przy zapisie skutków dokumentu
    assert zatwierdz(fabryka, kod) == "FV/2/09/2026"


def test_dwa_rownolegle_zatwierdzenia_nie_dostaja_tego_samego_numeru(fabryka, nowa_seria):
    kod = nowa_seria()
    start = threading.Barrier(2)
    wyniki: list[tuple[int, float]] = []
    bledy: list[BaseException] = []

    def zatwierdzenie() -> None:
        try:
            with fabryka.begin() as sesja:
                start.wait()
                numer = przydziel_numer(sesja, kod, WRZESIEN)
                wyniki.append((numer.kolejny, time.monotonic()))
                time.sleep(0.5)  # zapis dokumentu i skutków — blokada licznika trwa
        except BaseException as e:  # noqa: BLE001
            bledy.append(e)

    watki = [threading.Thread(target=zatwierdzenie) for _ in range(2)]
    for w in watki:
        w.start()
    for w in watki:
        w.join(timeout=10)

    assert not bledy
    assert sorted(n for n, _ in wyniki) == [1, 2]
    # Drugie zatwierdzenie musiało CZEKAĆ na commit pierwszego (blokada wiersza licznika).
    (_, t1), (_, t2) = sorted(wyniki)
    assert t2 - t1 >= 0.4


def test_rownolegle_wycofanie_nie_zostawia_dziury(fabryka, nowa_seria):
    kod = nowa_seria()
    start = threading.Barrier(2)
    zatwierdzone: list[int] = []

    def zatwierdzenie(wycofaj: bool) -> None:
        with fabryka() as sesja:
            sesja.begin()
            start.wait()
            numer = przydziel_numer(sesja, kod, WRZESIEN)
            time.sleep(0.3)
            if wycofaj:
                sesja.rollback()
            else:
                sesja.commit()
                zatwierdzone.append(numer.kolejny)

    watki = [threading.Thread(target=zatwierdzenie, args=(w,)) for w in (True, False)]
    for w in watki:
        w.start()
    for w in watki:
        w.join(timeout=10)

    assert zatwierdzone == [1]
    assert zatwierdz(fabryka, kod) == "FV/2/09/2026"


def test_wiele_rownoleglych_zatwierdzen_daje_ciagla_numeracje(fabryka, nowa_seria):
    kod = nowa_seria()
    wyniki: list[int] = []
    blokada = threading.Lock()

    def seria_zatwierdzen() -> None:
        for _ in range(10):
            with fabryka.begin() as sesja:
                kolejny = przydziel_numer(sesja, kod, WRZESIEN).kolejny
            with blokada:
                wyniki.append(kolejny)

    watki = [threading.Thread(target=seria_zatwierdzen) for _ in range(8)]
    for w in watki:
        w.start()
    for w in watki:
        w.join(timeout=30)

    assert sorted(wyniki) == list(range(1, 81))
