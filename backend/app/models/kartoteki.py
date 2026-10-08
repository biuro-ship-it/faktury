from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baza import Baza

TYPY_KONTRAHENTA = ("firma", "osoba_fizyczna")
TYPY_TOWARU = ("towar_handlowy", "surowiec", "wyrob_gotowy", "usluga")
# Kody GTU z JPK_V7 / FA(3): GTU_01 … GTU_13.
WZORZEC_GTU = r"^GTU_(0[1-9]|1[0-3])$"


class Kontrahent(Baza):
    """Odbiorca i/lub dostawca. Rekordów się nie usuwa (będą na nich dokumenty) — tylko wyłącza.
    Dokumenty zapiszą KOPIĘ danych kontrahenta, więc zmiana tutaj nie ruszy wystawionych faktur."""

    __tablename__ = "kontrahent"
    __table_args__ = (
        CheckConstraint(f"typ IN {TYPY_KONTRAHENTA}", name="typ"),
        CheckConstraint("jest_odbiorca OR jest_dostawca", name="rola"),
        CheckConstraint("length(trim(nazwa)) > 0", name="nazwa_niepusta"),
        CheckConstraint(
            "termin_platnosci_dni IS NULL OR termin_platnosci_dni BETWEEN 0 AND 365", name="termin_platnosci"
        ),
        # Jeden NIP = jeden kontrahent (puste NIP-y — osoby fizyczne, zagranica — się nie liczą).
        Index("uq_kontrahent_nip", "nip", unique=True, postgresql_where=text("nip <> ''")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    typ: Mapped[str] = mapped_column(String(20), default="firma", server_default="firma")
    nazwa: Mapped[str] = mapped_column(String(250))
    nip: Mapped[str] = mapped_column(String(10), default="", server_default="")
    nr_vat_ue: Mapped[str] = mapped_column(String(20), default="", server_default="")
    regon: Mapped[str] = mapped_column(String(14), default="", server_default="")
    adres_ulica: Mapped[str] = mapped_column(String(200), default="", server_default="")
    kod_pocztowy: Mapped[str] = mapped_column(String(10), default="", server_default="")
    miejscowosc: Mapped[str] = mapped_column(String(100), default="", server_default="")
    kraj: Mapped[str] = mapped_column(String(2), default="PL", server_default="PL")
    email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    telefon: Mapped[str] = mapped_column(String(30), default="", server_default="")
    jest_odbiorca: Mapped[bool] = mapped_column(default=True, server_default="true")
    jest_dostawca: Mapped[bool] = mapped_column(default=False, server_default="false")
    # NULL = obowiązuje termin domyślny z ustawień firmy.
    termin_platnosci_dni: Mapped[int | None] = mapped_column(SmallInteger)
    uwagi: Mapped[str] = mapped_column(Text, default="", server_default="")
    aktywny: Mapped[bool] = mapped_column(default=True, server_default="true", index=True)
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zmieniono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Towar(Baza):
    """Towar handlowy, surowiec, wyrób gotowy albo usługa. Usługi nie wchodzą na magazyn.
    Cena w groszach (int) — niezmiennik projektu: zero floatów."""

    __tablename__ = "towar"
    __table_args__ = (
        CheckConstraint(f"typ IN {TYPY_TOWARU}", name="typ"),
        CheckConstraint(f"gtu IS NULL OR gtu ~ '{WZORZEC_GTU}'", name="gtu"),
        CheckConstraint("cena_sprzedazy_netto IS NULL OR cena_sprzedazy_netto >= 0", name="cena"),
        CheckConstraint("length(trim(nazwa)) > 0", name="nazwa_niepusta"),
        CheckConstraint("length(trim(symbol)) > 0", name="symbol_niepusty"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), unique=True)  # zawsze WIELKIMI literami
    nazwa: Mapped[str] = mapped_column(String(250))
    typ: Mapped[str] = mapped_column(String(20), index=True)
    jm: Mapped[str] = mapped_column(String(10), default="szt.", server_default="szt.")
    stawka_vat_kod: Mapped[str] = mapped_column(ForeignKey("stawka_vat.kod", ondelete="RESTRICT"))
    gtu: Mapped[str | None] = mapped_column(String(6))
    cena_sprzedazy_netto: Mapped[int | None] = mapped_column(BigInteger)  # grosze za 1 jm
    ean: Mapped[str] = mapped_column(String(14), default="", server_default="")
    uwagi: Mapped[str] = mapped_column(Text, default="", server_default="")
    aktywny: Mapped[bool] = mapped_column(default=True, server_default="true", index=True)
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zmieniono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Pracownik(Baza):
    """Kartoteka pracowników (bez PESEL-u, kont i wynagrodzeń — to nie moduł kadrowo-płacowy)."""

    __tablename__ = "pracownik"
    __table_args__ = (
        CheckConstraint("length(trim(imie)) > 0 AND length(trim(nazwisko)) > 0", name="imie_nazwisko"),
        CheckConstraint(
            "data_zwolnienia IS NULL OR data_zatrudnienia IS NULL OR data_zwolnienia >= data_zatrudnienia",
            name="daty",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    imie: Mapped[str] = mapped_column(String(100))
    nazwisko: Mapped[str] = mapped_column(String(100))
    stanowisko: Mapped[str] = mapped_column(String(100), default="", server_default="")
    email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    telefon: Mapped[str] = mapped_column(String(30), default="", server_default="")
    data_zatrudnienia: Mapped[date | None] = mapped_column(Date)
    data_zwolnienia: Mapped[date | None] = mapped_column(Date)
    uwagi: Mapped[str] = mapped_column(Text, default="", server_default="")
    aktywny: Mapped[bool] = mapped_column(default=True, server_default="true", index=True)
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zmieniono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
