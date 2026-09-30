"""Niezmiennik pkt 4: kwoty w groszach (int), zero floatów."""

from decimal import Decimal

import pytest

from app.core.pieniadze import BladKwoty, na_tekst, vat_od_netto, wartosc_pozycji, z_tekstu


@pytest.mark.parametrize(
    ("tekst", "grosze"),
    [("12,34", 1234), ("12.34", 1234), ("1 234,50", 123450), ("1 234,5", 123450),
     ("-0,01", -1), ("0", 0), ("  7 ", 700)],
)
def test_z_tekstu(tekst, grosze):
    assert z_tekstu(tekst) == grosze


@pytest.mark.parametrize("tekst", ["1,234", "abc", "", "1,2,3", "NaN", "Infinity"])
def test_z_tekstu_odrzuca_bledne(tekst):
    with pytest.raises(BladKwoty):
        z_tekstu(tekst)


def test_float_jest_odrzucany_wszedzie():
    with pytest.raises(BladKwoty):
        z_tekstu(12.34)  # type: ignore[arg-type]
    with pytest.raises(BladKwoty):
        na_tekst(12.34)  # type: ignore[arg-type]
    with pytest.raises(BladKwoty):
        vat_od_netto(1000.0, 23)  # type: ignore[arg-type]
    with pytest.raises(BladKwoty):
        wartosc_pozycji(1.5, 100)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("grosze", "tekst"),
    [(1234567, "12 345,67"), (5, "0,05"), (-150, "-1,50"), (0, "0,00")],
)
def test_na_tekst(grosze, tekst):
    assert na_tekst(grosze) == tekst


@pytest.mark.parametrize(
    ("netto", "stawka", "vat"),
    [(10000, 23, 2300), (50, 23, 12), (3, 23, 1), (1, 23, 0), (-50, 23, -12), (999, 8, 80), (1000, 0, 0)],
)
def test_vat_od_netto_zaokragla_polowke_w_gore(netto, stawka, vat):
    assert vat_od_netto(netto, stawka) == vat


def test_wartosc_pozycji():
    assert wartosc_pozycji(Decimal("1.5"), 333) == 500  # 499,5 gr → 500
    assert wartosc_pozycji(Decimal("0.0001"), 100000) == 10
    assert wartosc_pozycji(Decimal("-2"), 1999) == -3998
