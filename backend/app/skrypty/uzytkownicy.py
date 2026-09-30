"""Zarządzanie allowlistą z wiersza poleceń (pierwszy admin nie ma jak dodać się przez UI).

    python -m app.skrypty.uzytkownicy dodaj info@pluszek.pl --imie Krzysiek --rola admin
    python -m app.skrypty.uzytkownicy lista
    python -m app.skrypty.uzytkownicy wylacz jan@pluszek.pl
    python -m app.skrypty.uzytkownicy wlacz jan@pluszek.pl
"""

import argparse
import sys

from sqlalchemy import select

from app.core.dziennik import zapisz_zdarzenie
from app.db import FabrykaSesji
from app.models import Uzytkownik
from app.models.uzytkownik import ROLE


def dodaj(email: str, imie: str, rola: str) -> None:
    with FabrykaSesji.begin() as sesja:
        if sesja.scalar(select(Uzytkownik).where(Uzytkownik.email == email)):
            sys.exit(f"Użytkownik {email} już istnieje.")
        u = Uzytkownik(email=email, imie=imie, rola=rola)
        sesja.add(u)
        sesja.flush()
        zapisz_zdarzenie(
            sesja, "uzytkownik.dodany", uzytkownik_id=None, encja="uzytkownik", encja_id=u.id,
            po={"email": email, "imie": imie, "rola": rola}, opis="skrypt CLI",
        )
    print(f"Dodano {email} ({rola}).")


def ustaw_aktywny(email: str, aktywny: bool) -> None:
    with FabrykaSesji.begin() as sesja:
        u = sesja.scalar(select(Uzytkownik).where(Uzytkownik.email == email))
        if u is None:
            sys.exit(f"Nie ma użytkownika {email}.")
        przed = {"aktywny": u.aktywny}
        u.aktywny = aktywny
        zapisz_zdarzenie(
            sesja, "uzytkownik.wlaczony" if aktywny else "uzytkownik.wylaczony",
            uzytkownik_id=None, encja="uzytkownik", encja_id=u.id,
            przed=przed, po={"aktywny": aktywny}, opis="skrypt CLI",
        )
    print(f"{email}: {'włączony' if aktywny else 'wyłączony'}.")


def lista() -> None:
    with FabrykaSesji() as sesja:
        for u in sesja.scalars(select(Uzytkownik).order_by(Uzytkownik.email)):
            stan = "aktywny" if u.aktywny else "WYŁĄCZONY"
            print(f"{u.email:<40} {u.rola:<11} {stan:<10} {u.imie}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Allowlista użytkowników Pluszek Księgowość")
    pod = parser.add_subparsers(dest="polecenie", required=True)
    p = pod.add_parser("dodaj")
    p.add_argument("email")
    p.add_argument("--imie", default="")
    p.add_argument("--rola", choices=ROLE, default="uzytkownik")
    pod.add_parser("lista")
    pod.add_parser("wylacz").add_argument("email")
    pod.add_parser("wlacz").add_argument("email")
    a = parser.parse_args()

    if a.polecenie == "dodaj":
        dodaj(a.email.strip().lower(), a.imie, a.rola)
    elif a.polecenie == "lista":
        lista()
    else:
        ustaw_aktywny(a.email.strip().lower(), a.polecenie == "wlacz")


if __name__ == "__main__":
    main()
