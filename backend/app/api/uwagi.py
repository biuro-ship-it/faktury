from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.zaleznosci import pobierz_uzytkownika
from app.core.dziennik import zapisz_zdarzenie
from app.db import pobierz_sesje
from app.models import Uwaga, Uzytkownik

router = APIRouter(prefix="/api/uwagi", tags=["uwagi"])

TypUwagi = Literal["poprawka", "pomysl", "blad"]
StatusUwagi = Literal["nowa", "w_realizacji", "zrobiona", "odrzucona"]


class NowaUwaga(BaseModel):
    tresc: str = Field(min_length=1, max_length=5000)
    typ: TypUwagi = "poprawka"
    modul: str | None = Field(default=None, max_length=40)


class ZmianaUwagi(BaseModel):
    status: StatusUwagi


class UwagaOut(BaseModel):
    id: int
    tresc: str
    typ: str
    modul: str | None
    status: str
    autor: str
    utworzono: datetime
    zmieniono: datetime | None


def _out(u: Uwaga, autor: Uzytkownik) -> UwagaOut:
    return UwagaOut(
        id=u.id, tresc=u.tresc, typ=u.typ, modul=u.modul, status=u.status,
        autor=autor.imie or autor.email, utworzono=u.utworzono, zmieniono=u.zmieniono,
    )


@router.get("", response_model=list[UwagaOut])
def lista(
    sesja: Session = Depends(pobierz_sesje),
    _: Uzytkownik = Depends(pobierz_uzytkownika),
) -> list[UwagaOut]:
    wiersze = sesja.execute(
        select(Uwaga, Uzytkownik).join(Uzytkownik, Uwaga.autor_id == Uzytkownik.id).order_by(Uwaga.id.desc())
    ).all()
    return [_out(u, a) for u, a in wiersze]


@router.post("", response_model=UwagaOut, status_code=status.HTTP_201_CREATED)
def dodaj(
    dane: NowaUwaga,
    sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> UwagaOut:
    tresc = dane.tresc.strip()
    if not tresc:
        raise HTTPException(422, "Treść uwagi nie może być pusta")
    uwaga = Uwaga(tresc=tresc, typ=dane.typ, modul=dane.modul, autor_id=uzytkownik.id)
    sesja.add(uwaga)
    sesja.flush()
    zapisz_zdarzenie(
        sesja, "uwaga.dodana", uzytkownik_id=uzytkownik.id, encja="uwaga", encja_id=uwaga.id,
        po={"typ": uwaga.typ, "modul": uwaga.modul, "tresc": tresc},
    )
    sesja.commit()
    sesja.refresh(uwaga)
    return _out(uwaga, uzytkownik)


@router.patch("/{uwaga_id}", response_model=UwagaOut)
def zmien_status(
    uwaga_id: int,
    dane: ZmianaUwagi,
    sesja: Session = Depends(pobierz_sesje),
    uzytkownik: Uzytkownik = Depends(pobierz_uzytkownika),
) -> UwagaOut:
    uwaga = sesja.get(Uwaga, uwaga_id, with_for_update=True)
    if uwaga is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie ma takiej uwagi")
    przed = uwaga.status
    if przed != dane.status:
        uwaga.status = dane.status
        uwaga.zmieniono = datetime.now(UTC)
        zapisz_zdarzenie(
            sesja, "uwaga.status", uzytkownik_id=uzytkownik.id, encja="uwaga", encja_id=uwaga.id,
            przed={"status": przed}, po={"status": dane.status},
        )
        sesja.commit()
    autor = sesja.get(Uzytkownik, uwaga.autor_id)
    assert autor is not None
    return _out(uwaga, autor)
