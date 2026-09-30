from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baza import Baza

FORMY_PLATNOSCI = ("przelew", "gotowka", "karta", "mobilna")


class Firma(Baza):
    """Dane sprzedawcy (Podmiot1 w FA(3)) i domyślne ustawienia faktur. Zawsze jeden wiersz (id=1).
    Faktury zapisują KOPIĘ tych danych, więc późniejsza zmiana nie ruszy wystawionych dokumentów."""

    __tablename__ = "firma"
    __table_args__ = (
        CheckConstraint("id = 1", name="jeden_wiersz"),
        CheckConstraint(f"forma_platnosci IN {FORMY_PLATNOSCI}", name="forma_platnosci"),
        CheckConstraint("termin_platnosci_dni BETWEEN 0 AND 365", name="termin_platnosci"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    nazwa: Mapped[str] = mapped_column(String(250), default="", server_default="")
    nazwa_skrocona: Mapped[str] = mapped_column(String(100), default="", server_default="")
    nip: Mapped[str] = mapped_column(String(10), default="", server_default="")
    regon: Mapped[str] = mapped_column(String(14), default="", server_default="")
    adres_ulica: Mapped[str] = mapped_column(String(200), default="", server_default="")
    kod_pocztowy: Mapped[str] = mapped_column(String(10), default="", server_default="")
    miejscowosc: Mapped[str] = mapped_column(String(100), default="", server_default="")
    kraj: Mapped[str] = mapped_column(String(2), default="PL", server_default="PL")
    email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    telefon: Mapped[str] = mapped_column(String(30), default="", server_default="")
    www: Mapped[str] = mapped_column(String(200), default="", server_default="")

    # Domyślne ustawienia faktur
    miejsce_wystawienia: Mapped[str] = mapped_column(String(100), default="", server_default="")
    termin_platnosci_dni: Mapped[int] = mapped_column(Integer, default=14, server_default="14")
    forma_platnosci: Mapped[str] = mapped_column(String(20), default="przelew", server_default="przelew")
    wystawiajacy: Mapped[str] = mapped_column(String(100), default="", server_default="")
    uwagi_na_fakturze: Mapped[str] = mapped_column(Text, default="", server_default="")

    zmieniono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KontoBankowe(Baza):
    __tablename__ = "konto_bankowe"
    __table_args__ = (
        CheckConstraint("waluta ~ '^[A-Z]{3}$'", name="waluta"),
        # Najwyżej jedno konto domyślne na walutę — pilnuje baza, nie tylko kod.
        Index("uq_konto_bankowe_domyslne", "waluta", unique=True, postgresql_where=text("domyslne")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nazwa: Mapped[str] = mapped_column(String(100))
    numer: Mapped[str] = mapped_column(String(34), unique=True)  # IBAN bez spacji
    bank: Mapped[str] = mapped_column(String(100), default="", server_default="")
    swift: Mapped[str] = mapped_column(String(11), default="", server_default="")
    waluta: Mapped[str] = mapped_column(String(3), default="PLN", server_default="PLN")
    domyslne: Mapped[bool] = mapped_column(default=False, server_default="false")
    aktywne: Mapped[bool] = mapped_column(default=True, server_default="true")
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StawkaVat(Baza):
    """Stawki z kodami pola P_12 schemy FA(3). Stawek się nie usuwa (będą na dokumentach) — tylko wyłącza."""

    __tablename__ = "stawka_vat"
    __table_args__ = (
        CheckConstraint("procent IS NULL OR procent BETWEEN 0 AND 100", name="procent"),
        Index("uq_stawka_vat_domyslna", "domyslna", unique=True, postgresql_where=text("domyslna")),
    )

    kod: Mapped[str] = mapped_column(String(10), primary_key=True)  # "23", "0 KR", "zw", "np I"…
    nazwa: Mapped[str] = mapped_column(String(100))
    procent: Mapped[int | None] = mapped_column(SmallInteger)  # NULL = zw / oo / np (brak kwoty VAT)
    kolejnosc: Mapped[int] = mapped_column(SmallInteger)
    aktywna: Mapped[bool] = mapped_column(default=True, server_default="true")
    domyslna: Mapped[bool] = mapped_column(default=False, server_default="false")
