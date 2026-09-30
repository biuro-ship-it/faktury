"""Niezmiennik pkt 5: dziennik zdarzeń zapisuje się razem z operacją i nie da się go zmienić."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.dziennik import zapisz_zdarzenie
from app.models import DziennikZdarzen


def _wpis(fabryka, unikalny) -> int:
    with fabryka.begin() as sesja:
        return zapisz_zdarzenie(
            sesja, "test.akcja", uzytkownik_id=None, encja="test", opis=unikalny,
            przed={"a": 1}, po={"a": 2},
        ).id


def test_wpis_zapisuje_stan_przed_i_po(fabryka, unikalny):
    id_wpisu = _wpis(fabryka, unikalny)
    with fabryka() as sesja:
        wpis = sesja.get(DziennikZdarzen, id_wpisu)
        assert (wpis.akcja, wpis.przed, wpis.po, wpis.opis) == ("test.akcja", {"a": 1}, {"a": 2}, unikalny)
        assert wpis.czas is not None


def test_wycofana_operacja_nie_zostawia_wpisu(fabryka, unikalny):
    with fabryka() as sesja:
        with sesja.begin():
            zapisz_zdarzenie(sesja, "test.wycofane", uzytkownik_id=None, opis=unikalny)
            sesja.rollback()
    with fabryka() as sesja:
        assert sesja.scalar(select(DziennikZdarzen).where(DziennikZdarzen.opis == unikalny)) is None


@pytest.mark.parametrize(
    "zapytanie",
    [
        "UPDATE dziennik_zdarzen SET akcja = 'podmiana' WHERE id = :id",
        "DELETE FROM dziennik_zdarzen WHERE id = :id",
        "TRUNCATE dziennik_zdarzen",
    ],
)
def test_dziennika_nie_da_sie_zmienic_ani_usunac(fabryka, unikalny, zapytanie):
    id_wpisu = _wpis(fabryka, unikalny)
    with fabryka() as sesja, pytest.raises(DBAPIError, match="tylko do dopisywania"):
        sesja.execute(text(zapytanie), {"id": id_wpisu})
    with fabryka() as sesja:
        assert sesja.get(DziennikZdarzen, id_wpisu).akcja == "test.akcja"
