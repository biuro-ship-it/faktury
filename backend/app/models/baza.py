from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Jawne nazwy ograniczeń — Alembic potrafi je potem zmieniać/usuwać w migracjach.
KONWENCJA_NAZW = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Baza(DeclarativeBase):
    metadata = MetaData(naming_convention=KONWENCJA_NAZW)
