from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baza import Baza

OKRESY_RESETU = ("miesiac", "rok", "brak")


class SeriaNumeracji(Baza):
    __tablename__ = "seria_numeracji"
    __table_args__ = (CheckConstraint(f"okres_resetu IN {OKRESY_RESETU}", name="okres_resetu"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kod: Mapped[str] = mapped_column(String(30), unique=True)  # np. "FV", "FK", "KP"
    typ_dokumentu: Mapped[str] = mapped_column(String(30))
    nazwa: Mapped[str] = mapped_column(String(100))
    # Zmienne: {nr} (można z dopełnieniem: {nr:04d}), {MM}, {RRRR}, {RR}.
    wzorzec: Mapped[str] = mapped_column(String(60))
    okres_resetu: Mapped[str] = mapped_column(String(10))
    aktywna: Mapped[bool] = mapped_column(default=True, server_default="true")
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LicznikNumeracji(Baza):
    """Jeden wiersz na serię i okres. Wiersz jest blokowany do końca transakcji
    zatwierdzającej dokument — to on gwarantuje brak dziur i duplikatów."""

    __tablename__ = "licznik_numeracji"
    __table_args__ = (CheckConstraint("ostatni_numer >= 0", name="nieujemny"),)

    seria_id: Mapped[int] = mapped_column(
        ForeignKey("seria_numeracji.id", ondelete="RESTRICT"), primary_key=True
    )
    okres: Mapped[str] = mapped_column(String(7), primary_key=True)  # "2026-09" / "2026" / "-"
    ostatni_numer: Mapped[int] = mapped_column(Integer)
