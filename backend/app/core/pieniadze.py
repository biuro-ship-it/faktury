"""Kwoty w groszach jako int (niezmiennik, pkt 4). Float jest odrzucany wszędzie —
0.1 + 0.2 != 0.3 to w księgowości błąd, nie ciekawostka."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

Grosze = int

_SETNA = Decimal("0.01")


class BladKwoty(ValueError):
    pass


def _zaokraglij_do_grosza(wartosc_w_groszach: Decimal) -> Grosze:
    # ROUND_HALF_UP w Decimal zaokrągla „od zera”, więc -0,5 gr → -1 gr (symetrycznie dla korekt).
    return int(wartosc_w_groszach.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def z_tekstu(tekst: str) -> Grosze:
    """„1 234,56” / „1234.56” / „-12,5” → grosze. Więcej niż 2 miejsca po przecinku = błąd."""
    if not isinstance(tekst, str):
        raise BladKwoty(f"Oczekiwano tekstu, a jest {type(tekst).__name__}")
    czysty = tekst.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        kwota = Decimal(czysty)
    except InvalidOperation as e:
        raise BladKwoty(f"Nieprawidłowa kwota: „{tekst}”") from e
    if not kwota.is_finite():
        raise BladKwoty(f"Nieprawidłowa kwota: „{tekst}”")
    if kwota != kwota.quantize(_SETNA):
        raise BladKwoty(f"Kwota ma więcej niż 2 miejsca po przecinku: „{tekst}”")
    return int(kwota * 100)


def na_tekst(grosze: Grosze) -> str:
    """1234567 → „12 345,67” (spacja twarda jako separator tysięcy)."""
    if not isinstance(grosze, int) or isinstance(grosze, bool):
        raise BladKwoty(f"Kwota musi być int (grosze), a jest {type(grosze).__name__}")
    znak = "-" if grosze < 0 else ""
    zlote, gr = divmod(abs(grosze), 100)
    return f"{znak}{zlote:,}".replace(",", " ") + f",{gr:02d}"


def vat_od_netto(netto: Grosze, stawka_procent: int) -> Grosze:
    """VAT od sumy netto w danej stawce (metoda zgodna z FA(3)), zaokrąglenie do grosza."""
    if not isinstance(netto, int) or not isinstance(stawka_procent, int):
        raise BladKwoty("netto i stawka muszą być int")
    return _zaokraglij_do_grosza(Decimal(netto) * stawka_procent / 100)


def wartosc_pozycji(ilosc: Decimal, cena_jednostkowa: Grosze) -> Grosze:
    """Ilość (NUMERIC(14,4)) × cena w groszach → grosze, zaokrąglenie do grosza."""
    if not isinstance(ilosc, Decimal):
        raise BladKwoty(f"Ilość musi być Decimal, a jest {type(ilosc).__name__}")
    if not isinstance(cena_jednostkowa, int):
        raise BladKwoty("Cena musi być int (grosze)")
    return _zaokraglij_do_grosza(ilosc * cena_jednostkowa)
