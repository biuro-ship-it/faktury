from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baza import Baza

TYPY_UWAG = ("poprawka", "pomysl", "blad")
STATUSY_UWAG = ("nowa", "w_realizacji", "zrobiona", "odrzucona")


class Uwaga(Baza):
    """Uwagi Krzyśka do aplikacji: co poprawić, co dopisać. Nie kasujemy — tylko zmiana statusu."""

    __tablename__ = "uwaga"
    __table_args__ = (
        CheckConstraint(f"typ IN {TYPY_UWAG}", name="typ"),
        CheckConstraint(f"status IN {STATUSY_UWAG}", name="status"),
        CheckConstraint("length(trim(tresc)) > 0", name="tresc_niepusta"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tresc: Mapped[str] = mapped_column(Text)
    typ: Mapped[str] = mapped_column(String(20))
    # Ścieżka modułu z menu (np. "/sprzedaz") albo NULL = ogólna.
    modul: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="nowa", server_default="nowa", index=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey("uzytkownik.id", ondelete="RESTRICT"))
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zmieniono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
