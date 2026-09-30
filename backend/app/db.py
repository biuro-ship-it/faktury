from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import ustawienia


def utworz_silnik(url: str) -> Engine:
    # pool_pre_ping: mydevil zrywa bezczynne połączenia, a Passenger trzyma proces długo.
    return create_engine(url, pool_pre_ping=True)


silnik = utworz_silnik(ustawienia().database_url)
FabrykaSesji = sessionmaker(silnik, expire_on_commit=False)


def pobierz_sesje() -> Iterator[Session]:
    with FabrykaSesji() as sesja:
        yield sesja
