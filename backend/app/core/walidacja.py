"""Walidacja polskich identyfikatorów: NIP (suma kontrolna) i numer rachunku (IBAN/NRB, mod 97)."""

import re

_WAGI_NIP = (6, 5, 7, 2, 3, 4, 5, 6, 7)


class BladWalidacji(ValueError):
    pass


def normalizuj_nip(nip: str) -> str:
    """„PL 123-456-32-18” → „1234563218”; błąd, gdy suma kontrolna się nie zgadza."""
    cyfry = re.sub(r"[\s-]", "", nip.strip().upper()).removeprefix("PL")
    if not re.fullmatch(r"\d{10}", cyfry):
        raise BladWalidacji("NIP musi mieć 10 cyfr")
    suma = sum(int(c) * w for c, w in zip(cyfry, _WAGI_NIP, strict=False)) % 11
    if suma == 10 or suma != int(cyfry[9]):
        raise BladWalidacji("Nieprawidłowy NIP (błędna suma kontrolna)")
    return cyfry


def normalizuj_iban(numer: str) -> str:
    """26 cyfr (NRB) albo IBAN z kodem kraju → „PL61109010140000071219812874”; kontrola mod 97."""
    czysty = re.sub(r"[\s-]", "", numer.strip().upper())
    if re.fullmatch(r"\d{26}", czysty):
        czysty = "PL" + czysty
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", czysty):
        raise BladWalidacji("Numer konta musi mieć 26 cyfr (albo format IBAN)")
    if czysty.startswith("PL") and len(czysty) != 28:
        raise BladWalidacji("Polski numer konta musi mieć 26 cyfr")
    przestawiony = czysty[4:] + czysty[:4]
    liczba = "".join(str(int(z, 36)) for z in przestawiony)
    if int(liczba) % 97 != 1:
        raise BladWalidacji("Nieprawidłowy numer konta (błędna suma kontrolna)")
    return czysty


def formatuj_iban(iban: str) -> str:
    """„PL61109010140000071219812874” → „PL61 1090 1014 0000 0712 1981 2874”."""
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
