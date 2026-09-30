from sqlalchemy import select

from app.models import DziennikZdarzen
from tests.test_api_logowanie import klient, naglowek, tokeny, uzytkownik  # noqa: F401 — fikstury

DOBRY = naglowek("dobry")


def test_uwagi_wymagaja_logowania(klient):  # noqa: F811
    assert klient.get("/api/uwagi").status_code == 401
    assert klient.post("/api/uwagi", json={"tresc": "x"}).status_code == 401


def test_dodanie_lista_i_zmiana_statusu(klient, fabryka, uzytkownik, unikalny):  # noqa: F811
    tresc = f"Dodać filtr po dacie na liście faktur {unikalny}"
    odp = klient.post("/api/uwagi", headers=DOBRY, json={"tresc": f"  {tresc}  ", "typ": "pomysl", "modul": "/sprzedaz"})
    assert odp.status_code == 201
    uwaga = odp.json()
    assert (uwaga["tresc"], uwaga["typ"], uwaga["modul"], uwaga["status"], uwaga["autor"]) == (
        tresc, "pomysl", "/sprzedaz", "nowa", "Krzysiek",
    )

    assert any(u["id"] == uwaga["id"] for u in klient.get("/api/uwagi", headers=DOBRY).json())

    odp = klient.patch(f"/api/uwagi/{uwaga['id']}", headers=DOBRY, json={"status": "zrobiona"})
    assert odp.status_code == 200
    assert odp.json()["status"] == "zrobiona" and odp.json()["zmieniono"] is not None

    with fabryka() as sesja:
        wpisy = sesja.scalars(
            select(DziennikZdarzen).where(DziennikZdarzen.encja == "uwaga", DziennikZdarzen.encja_id == uwaga["id"])
            .order_by(DziennikZdarzen.id)
        ).all()
    assert [w.akcja for w in wpisy] == ["uwaga.dodana", "uwaga.status"]
    assert (wpisy[1].przed, wpisy[1].po) == ({"status": "nowa"}, {"status": "zrobiona"})


def test_niepoprawne_dane(klient, uzytkownik):  # noqa: F811
    assert klient.post("/api/uwagi", headers=DOBRY, json={"tresc": "   "}).status_code == 422
    assert klient.post("/api/uwagi", headers=DOBRY, json={"tresc": "x", "typ": "inne"}).status_code == 422
    assert klient.patch("/api/uwagi/999999999", headers=DOBRY, json={"status": "zrobiona"}).status_code == 404
    uwaga = klient.post("/api/uwagi", headers=DOBRY, json={"tresc": "x"}).json()
    assert klient.patch(f"/api/uwagi/{uwaga['id']}", headers=DOBRY, json={"status": "skasowana"}).status_code == 422
