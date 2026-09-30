"""Testy działają na OSOBNEJ bazie (DATABASE_URL_TEST). Jej schemat jest kasowany
i odtwarzany migracjami Alembica na starcie — przy okazji testujemy same migracje.

Dane nie są czyszczone między testami (dziennik zdarzeń blokuje DELETE/TRUNCATE),
więc każdy test tworzy własne, unikalne dane (e-maile, kody serii).
"""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import KATALOG_BACKENDU, ustawienia
from app.db import utworz_silnik


@pytest.fixture(scope="session")
def silnik_testowy() -> Iterator[Engine]:
    url = ustawienia().database_url_test
    if not url:
        pytest.exit("Brak DATABASE_URL_TEST — testy potrzebują osobnej bazy.", returncode=2)
    # Bezpiecznik: testy kasują schemat, więc nigdy nie mogą trafić w bazę dev/produkcyjną.
    nazwa_bazy = make_url(url).database or ""
    if not nazwa_bazy.endswith("_test"):
        pytest.exit(f"Baza testowa musi mieć nazwę kończącą się na _test (jest: {nazwa_bazy}).", returncode=2)

    silnik = utworz_silnik(url)
    with silnik.begin() as polaczenie:
        polaczenie.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        polaczenie.execute(text("CREATE SCHEMA public"))

    konfiguracja = Config(str(KATALOG_BACKENDU / "alembic.ini"))
    konfiguracja.set_main_option("script_location", str(KATALOG_BACKENDU / "alembic"))
    konfiguracja.attributes["url"] = url
    command.upgrade(konfiguracja, "head")

    yield silnik
    silnik.dispose()


@pytest.fixture
def fabryka(silnik_testowy: Engine) -> sessionmaker[Session]:
    return sessionmaker(silnik_testowy, expire_on_commit=False)


@pytest.fixture
def unikalny() -> str:
    return uuid.uuid4().hex[:10]
