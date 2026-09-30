from typing import Any

from sqlalchemy.orm import Session

from app.models import DziennikZdarzen


def zapisz_zdarzenie(
    sesja: Session,
    akcja: str,
    *,
    uzytkownik_id: int | None,
    encja: str | None = None,
    encja_id: int | None = None,
    przed: dict[str, Any] | None = None,
    po: dict[str, Any] | None = None,
    opis: str | None = None,
) -> DziennikZdarzen:
    """Dodaje wpis w BIEŻĄCEJ transakcji — nie commituje. Dzięki temu wpis i operacja,
    którą opisuje, zapisują się razem albo wcale (niezmiennik, pkt 3 i 5)."""
    wpis = DziennikZdarzen(
        akcja=akcja,
        uzytkownik_id=uzytkownik_id,
        encja=encja,
        encja_id=encja_id,
        przed=przed,
        po=po,
        opis=opis,
    )
    sesja.add(wpis)
    sesja.flush()
    return wpis
