from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baza import Baza


class DziennikZdarzen(Baza):
    """Kto, kiedy, co, stan przed/po. Tylko dopisywanie — UPDATE/DELETE/TRUNCATE blokuje
    wyzwalacz w bazie (migracja 0001), więc nawet błąd w kodzie nie zmieni historii."""

    __tablename__ = "dziennik_zdarzen"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    czas: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # NULL = operacja systemowa (skrypt, migracja) albo nieudane logowanie spoza allowlisty.
    uzytkownik_id: Mapped[int | None] = mapped_column(
        ForeignKey("uzytkownik.id", ondelete="RESTRICT"), index=True
    )
    akcja: Mapped[str] = mapped_column(String(60), index=True)
    encja: Mapped[str | None] = mapped_column(String(60))
    encja_id: Mapped[int | None] = mapped_column(BigInteger)
    przed: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    po: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    opis: Mapped[str | None] = mapped_column(Text)
