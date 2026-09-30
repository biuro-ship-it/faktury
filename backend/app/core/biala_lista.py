"""Wykaz podatników VAT („Biała Lista” MF): dane podmiotu i zgłoszone rachunki po NIP.

API publiczne, bez klucza. Limit metody /search: 10 zapytań dziennie z jednego IP — używać na żądanie
(przycisk), nigdy w pętli. Dokumentacja: https://wl-api.mf.gov.pl
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import requests

URL = "https://wl-api.mf.gov.pl/api/search/nip/{nip}"


class BladBialejListy(Exception):
    pass


@dataclass
class DanePodmiotu:
    nazwa: str
    nip: str
    regon: str
    status_vat: str
    adres_ulica: str = ""
    kod_pocztowy: str = ""
    miejscowosc: str = ""
    konta: list[str] = field(default_factory=list)


def rozbij_adres(adres: str) -> tuple[str, str, str]:
    """„UL. KWIATOWA 1/2, 00-001 WARSZAWA” → („UL. KWIATOWA 1/2”, „00-001”, „WARSZAWA”)."""
    dopasowanie = re.fullmatch(r"\s*(.*?),?\s*(\d{2}-\d{3})\s+(.+?)\s*", adres or "")
    if not dopasowanie:
        return (adres or "").strip(), "", ""
    return dopasowanie.group(1).strip(" ,"), dopasowanie.group(2), dopasowanie.group(3)


def z_odpowiedzi(dane: dict[str, Any]) -> DanePodmiotu:
    podmiot = (dane.get("result") or {}).get("subject")
    if not podmiot:
        raise BladBialejListy("Nie znaleziono podmiotu o tym NIP w wykazie podatników VAT")
    ulica, kod, miasto = rozbij_adres(podmiot.get("workingAddress") or podmiot.get("residenceAddress") or "")
    return DanePodmiotu(
        nazwa=podmiot.get("name") or "",
        nip=podmiot.get("nip") or "",
        regon=podmiot.get("regon") or "",
        status_vat=podmiot.get("statusVat") or "",
        adres_ulica=ulica,
        kod_pocztowy=kod,
        miejscowosc=miasto,
        konta=list(podmiot.get("accountNumbers") or []),
    )


def pobierz(nip: str, na_dzien: date | None = None) -> DanePodmiotu:
    try:
        odpowiedz = requests.get(
            URL.format(nip=nip), params={"date": (na_dzien or date.today()).isoformat()}, timeout=15
        )
    except requests.RequestException as e:
        raise BladBialejListy("Brak połączenia z Białą Listą MF — spróbuj później") from e
    if odpowiedz.status_code == 429:
        raise BladBialejListy("Przekroczony dzienny limit zapytań do Białej Listy MF — spróbuj jutro")
    if odpowiedz.status_code == 400:
        komunikat = (odpowiedz.json() or {}).get("message", "") if odpowiedz.content else ""
        raise BladBialejListy(f"Biała Lista odrzuciła zapytanie. {komunikat}".strip())
    if not odpowiedz.ok:
        raise BladBialejListy(f"Biała Lista MF zwróciła błąd {odpowiedz.status_code}")
    return z_odpowiedzi(odpowiedz.json())
