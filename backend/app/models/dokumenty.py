"""Dokumenty handlowe: faktury sprzedaży i zakupu (a docelowo także korekty, proformy i faktury kosztowe).

Jedna tabela `dokument` dla wszystkich faktur — PLAN.md, sekcja 5. Niezmiennik (PLAN, sekcja 3):
- zatwierdzonego dokumentu nie wolno zmienić ani usunąć; jedyna zmiana to anulowanie (numer zostaje zajęty).
  Pilnuje tego także WYZWALACZ w bazie (migracja 0005), nie tylko kod;
- numer nadaje się dopiero przy zatwierdzeniu, w tej samej transakcji (app/core/numeracja.py);
- dokument przechowuje KOPIĘ danych nabywcy, sprzedawcy i pozycji — późniejsza zmiana kartotek czy
  ustawień firmy nie rusza wystawionych faktur;
- kwoty w groszach (BIGINT), ilości NUMERIC(14,4).

Faktura ZAKUPU używa tych samych kolumn „na odwrót” (nazwy zostały z faktury sprzedaży, żeby nie ruszać
wdrożonej migracji 0005): kolumny `nabywca_*` przechowują KOPIĘ DANYCH DOSTAWCY (kontrahenta), a JSONB
`sprzedawca` — kopię danych WŁASNEJ firmy (nabywcy tej faktury). Warstwa API (app/api/zakupy.py) pokazuje je
pod właściwymi nazwami (`dostawca_*`, `nabywca`). `numer` to numer nadany w aplikacji (własna seria),
`numer_obcy` — numer faktury dostawcy.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.baza import Baza
from app.models.ustawienia import FORMY_PLATNOSCI

TYPY_DOKUMENTU = ("faktura_sprzedazy", "korekta_sprzedazy", "proforma", "faktura_zakupu", "faktura_kosztowa")
STATUSY_DOKUMENTU = ("szkic", "zatwierdzony", "anulowany")


class Dokument(Baza):
    __tablename__ = "dokument"
    __table_args__ = (
        CheckConstraint(f"typ IN {TYPY_DOKUMENTU}", name="typ"),
        CheckConstraint(f"status IN {STATUSY_DOKUMENTU}", name="status"),
        CheckConstraint(f"forma_platnosci IN {FORMY_PLATNOSCI}", name="forma_platnosci"),
        # Poza szkicem dokument MUSI mieć numer, serię, nabywcę i kopię danych sprzedawcy.
        CheckConstraint(
            "status = 'szkic' OR (numer IS NOT NULL AND seria_id IS NOT NULL AND kontrahent_id IS NOT NULL"
            " AND sprzedawca IS NOT NULL AND zatwierdzono IS NOT NULL)",
            name="zatwierdzony_kompletny",
        ),
        CheckConstraint("status <> 'anulowany' OR anulowano IS NOT NULL", name="anulowany_kompletny"),
        CheckConstraint("suma_brutto = suma_netto + suma_vat", name="suma_brutto"),
        CheckConstraint("termin_platnosci IS NULL OR termin_platnosci >= data_wystawienia", name="termin"),
        CheckConstraint("waluta ~ '^[A-Z]{3}$'", name="waluta"),
        # Numer jest unikalny w obrębie typu dokumentu (dwie serie nie mogą wyprodukować tego samego numeru).
        Index("uq_dokument_typ_numer", "typ", "numer", unique=True, postgresql_where=text("numer IS NOT NULL")),
        Index("ix_dokument_typ_data", "typ", "data_wystawienia"),
        # Faktura zakupu zatwierdzona musi mieć numer dostawcy (migracja 0006).
        CheckConstraint(
            "typ <> 'faktura_zakupu' OR status = 'szkic' OR length(btrim(numer_obcy)) > 0", name="zakup_numer_obcy"
        ),
        # Ten sam numer faktury dostawcy nie może trafić do ewidencji dwa razy (podwójne naliczenie VAT).
        # Anulowana faktura zwalnia numer — można wprowadzić ją poprawnie od nowa.
        Index(
            "uq_dokument_zakupu_numer_obcy", "kontrahent_id", "numer_obcy", unique=True,
            postgresql_where=text("typ = 'faktura_zakupu' AND status <> 'anulowany' AND numer_obcy <> ''"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    typ: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(15), default="szkic", server_default="szkic", index=True)
    seria_id: Mapped[int | None] = mapped_column(ForeignKey("seria_numeracji.id", ondelete="RESTRICT"))
    numer: Mapped[str | None] = mapped_column(String(60))
    # Numer dokumentu kontrahenta — dla faktur zakupu i kosztowych (faza 2, moduły Zakupy/Koszty).
    numer_obcy: Mapped[str] = mapped_column(String(60), default="", server_default="")
    dokument_korygowany_id: Mapped[int | None] = mapped_column(ForeignKey("dokument.id", ondelete="RESTRICT"))

    data_wystawienia: Mapped[date] = mapped_column(Date)
    data_sprzedazy: Mapped[date] = mapped_column(Date)  # data dostawy / wykonania usługi (P_6 w FA(3))
    termin_platnosci: Mapped[date | None] = mapped_column(Date)
    forma_platnosci: Mapped[str] = mapped_column(String(20), default="przelew", server_default="przelew")
    miejsce_wystawienia: Mapped[str] = mapped_column(String(100), default="", server_default="")
    waluta: Mapped[str] = mapped_column(String(3), default="PLN", server_default="PLN")

    # Nabywca: odnośnik do kartoteki + KOPIA danych z chwili zatwierdzenia (w szkicu — z chwili zapisu).
    kontrahent_id: Mapped[int | None] = mapped_column(ForeignKey("kontrahent.id", ondelete="RESTRICT"), index=True)
    nabywca_nazwa: Mapped[str] = mapped_column(String(250), default="", server_default="")
    nabywca_nip: Mapped[str] = mapped_column(String(10), default="", server_default="")
    nabywca_nr_vat_ue: Mapped[str] = mapped_column(String(20), default="", server_default="")
    nabywca_adres_ulica: Mapped[str] = mapped_column(String(200), default="", server_default="")
    nabywca_kod_pocztowy: Mapped[str] = mapped_column(String(10), default="", server_default="")
    nabywca_miejscowosc: Mapped[str] = mapped_column(String(100), default="", server_default="")
    nabywca_kraj: Mapped[str] = mapped_column(String(2), default="PL", server_default="PL")

    # Sprzedawca (Podmiot1 w FA(3)) i rachunek do zapłaty — kopia z Ustawień z chwili zatwierdzenia.
    sprzedawca: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    konto_bankowe_id: Mapped[int | None] = mapped_column(ForeignKey("konto_bankowe.id", ondelete="RESTRICT"))

    suma_netto: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    suma_vat: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    suma_brutto: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    wystawiajacy: Mapped[str] = mapped_column(String(100), default="", server_default="")
    uwagi: Mapped[str] = mapped_column(Text, default="", server_default="")

    # KSeF (faza 8) — pola są od początku, puste do czasu integracji.
    ksef_numer: Mapped[str | None] = mapped_column(String(50))
    ksef_status: Mapped[str | None] = mapped_column(String(20))
    ksef_xml: Mapped[str | None] = mapped_column(Text)
    ksef_upo: Mapped[str | None] = mapped_column(Text)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    utworzyl_id: Mapped[int | None] = mapped_column(ForeignKey("uzytkownik.id", ondelete="RESTRICT"))
    zmieniono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    zatwierdzono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    zatwierdzil_id: Mapped[int | None] = mapped_column(ForeignKey("uzytkownik.id", ondelete="RESTRICT"))
    anulowano: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulowal_id: Mapped[int | None] = mapped_column(ForeignKey("uzytkownik.id", ondelete="RESTRICT"))
    przyczyna_anulowania: Mapped[str] = mapped_column(Text, default="", server_default="")

    pozycje: Mapped[list["DokumentPozycja"]] = relationship(
        back_populates="dokument", order_by="DokumentPozycja.lp", cascade="all, delete-orphan"
    )
    stawki: Mapped[list["DokumentStawka"]] = relationship(
        back_populates="dokument", order_by="DokumentStawka.kolejnosc", cascade="all, delete-orphan"
    )


class DokumentPozycja(Baza):
    """Pozycja z KOPIĄ nazwy, j.m., ceny i stawki — towar w kartotece może się później zmienić."""

    __tablename__ = "dokument_pozycja"
    __table_args__ = (
        UniqueConstraint("dokument_id", "lp", name="uq_dokument_pozycja_lp"),
        CheckConstraint("ilosc <> 0", name="ilosc"),
        CheckConstraint("cena_netto >= 0", name="cena"),
        CheckConstraint("length(trim(nazwa)) > 0", name="nazwa_niepusta"),
        CheckConstraint("gtu IS NULL OR gtu ~ '^GTU_(0[1-9]|1[0-3])$'", name="gtu"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dokument_id: Mapped[int] = mapped_column(ForeignKey("dokument.id", ondelete="CASCADE"), index=True)
    lp: Mapped[int] = mapped_column(SmallInteger)
    towar_id: Mapped[int | None] = mapped_column(ForeignKey("towar.id", ondelete="RESTRICT"), index=True)
    nazwa: Mapped[str] = mapped_column(String(500))
    jm: Mapped[str] = mapped_column(String(10))
    ilosc: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    cena_netto: Mapped[int] = mapped_column(BigInteger)  # grosze za 1 j.m.
    stawka_vat_kod: Mapped[str] = mapped_column(ForeignKey("stawka_vat.kod", ondelete="RESTRICT"))
    gtu: Mapped[str | None] = mapped_column(String(6))
    wartosc_netto: Mapped[int] = mapped_column(BigInteger)  # ilość × cena, zaokrąglone do grosza

    dokument: Mapped[Dokument] = relationship(back_populates="pozycje")


class DokumentStawka(Baza):
    """Podsumowanie dokumentu w stawce VAT (P_13_x / P_14_x w FA(3)). VAT liczony od SUMY netto w stawce,
    nie od pozycji — dlatego jest zapisany, a nie wyliczany w raportach z pozycji."""

    __tablename__ = "dokument_stawka"
    __table_args__ = (CheckConstraint("brutto = netto + vat", name="brutto"),)

    dokument_id: Mapped[int] = mapped_column(ForeignKey("dokument.id", ondelete="CASCADE"), primary_key=True)
    stawka_vat_kod: Mapped[str] = mapped_column(
        ForeignKey("stawka_vat.kod", ondelete="RESTRICT"), primary_key=True
    )
    kolejnosc: Mapped[int] = mapped_column(SmallInteger)
    netto: Mapped[int] = mapped_column(BigInteger)
    vat: Mapped[int] = mapped_column(BigInteger)
    brutto: Mapped[int] = mapped_column(BigInteger)

    dokument: Mapped[Dokument] = relationship(back_populates="stawki")
