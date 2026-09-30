"""Otwarte uwagi (nowe i w realizacji) — do przeczytania na początku sesji pracy nad aplikacją.

    python -m app.skrypty.uwagi            # otwarte
    python -m app.skrypty.uwagi --wszystkie
"""

import argparse

from sqlalchemy import select

from app.db import FabrykaSesji
from app.models import Uwaga


def main() -> None:
    parser = argparse.ArgumentParser(description="Lista uwag do aplikacji")
    parser.add_argument("--wszystkie", action="store_true", help="także zrobione i odrzucone")
    a = parser.parse_args()

    zapytanie = select(Uwaga).order_by(Uwaga.id)
    if not a.wszystkie:
        zapytanie = zapytanie.where(Uwaga.status.in_(("nowa", "w_realizacji")))
    with FabrykaSesji() as sesja:
        uwagi = sesja.scalars(zapytanie).all()
    if not uwagi:
        print("Brak uwag.")
    for u in uwagi:
        print(f"#{u.id} [{u.status}] {u.typ} · {u.modul or 'cała aplikacja'} · {u.utworzono:%Y-%m-%d %H:%M}")
        print(f"    {u.tresc}")


if __name__ == "__main__":
    main()
