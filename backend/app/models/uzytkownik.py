from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baza import Baza

ROLE = ("admin", "uzytkownik")


class Uzytkownik(Baza):
    """Allowlista: do aplikacji wejdzie tylko aktywny e-mail z tej tabeli."""

    __tablename__ = "uzytkownik"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_male_litery"),
        CheckConstraint(f"rola IN {ROLE}", name="rola"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    imie: Mapped[str] = mapped_column(String(100), default="", server_default="")
    rola: Mapped[str] = mapped_column(String(20), default="uzytkownik", server_default="uzytkownik")
    aktywny: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Ostatni UID Firebase, z którym się logował — do audytu, nie do autoryzacji.
    firebase_uid: Mapped[str | None] = mapped_column(String(128))
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ostatnie_logowanie: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
