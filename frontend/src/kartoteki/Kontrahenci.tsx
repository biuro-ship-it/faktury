import { Download, Mail, MapPin, Phone, Plus, UserRound, Users } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Komunikat, Pole, Przycisk, PoleTekstowe, Wejscie, Wybor } from '../ui/formularz'
import {
  Awatar, NA_STRONE, Paginacja, Panel, Plakietka, Segmenty, SekcjaFormularza, Szukajka, StanPusty, SzkieletWierszy,
  useOpoznione,
} from '../ui/kartoteka'
import { pobierzZBialejListy } from '../ustawienia/api'
import {
  type Aktywnosc, type Kontrahent, type KontrahentDane, PUSTY_KONTRAHENT, type RolaKontrahenta, useKontrahenci,
  useZapiszKontrahenta,
} from './api'

const AKTYWNOSC = [
  { wartosc: 'tak', nazwa: 'Aktywni' },
  { wartosc: 'nie', nazwa: 'Wyłączeni' },
  { wartosc: 'wszystkie', nazwa: 'Wszyscy' },
] as const
const ROLE = [
  { wartosc: 'wszyscy', nazwa: 'Wszyscy' },
  { wartosc: 'odbiorcy', nazwa: 'Odbiorcy' },
  { wartosc: 'dostawcy', nazwa: 'Dostawcy' },
] as const

type Otwarty = { id: number | null; dane: KontrahentDane } | null

export function Kontrahenci() {
  const [q, setQ] = useState('')
  const [aktywnosc, setAktywnosc] = useState<Aktywnosc>('tak')
  const [rola, setRola] = useState<RolaKontrahenta>('wszyscy')
  const [offset, setOffset] = useState(0)
  const [otwarty, setOtwarty] = useState<Otwarty>(null)
  const szukane = useOpoznione(q)
  const lista = useKontrahenci({ q: szukane, aktywnosc, offset, limit: NA_STRONE }, rola)
  const filtrowane = szukane.trim() !== '' || aktywnosc !== 'tak' || rola !== 'wszyscy'
  const nowy = () => setOtwarty({ id: null, dane: PUSTY_KONTRAHENT })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Szukajka wartosc={q} onZmiana={(v) => { setQ(v); setOffset(0) }} placeholder="Szukaj po nazwie, NIP, mieście, e-mailu…" />
        <Segmenty etykieta="Rola" opcje={[...ROLE]} wartosc={rola} onZmiana={(v) => { setRola(v); setOffset(0) }} />
        <Segmenty etykieta="Status" opcje={[...AKTYWNOSC]} wartosc={aktywnosc} onZmiana={(v) => { setAktywnosc(v); setOffset(0) }} />
        <Przycisk className="ml-auto" onClick={nowy}><Plus className="size-4" /> Nowy kontrahent</Przycisk>
      </div>

      <section className="overflow-hidden rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
        {lista.isPending ? (
          <SzkieletWierszy />
        ) : lista.isError ? (
          <div className="p-5"><Komunikat rodzaj="blad">{lista.error.message}</Komunikat></div>
        ) : lista.data.pozycje.length === 0 ? (
          <StanPusty
            filtrowane={filtrowane} ikona={<Users className="size-6" />} tytul="Brak kontrahentów"
            opis="Dodaj pierwszego odbiorcę albo dostawcę. Dane firmy pobierzesz z Białej Listy MF po samym NIP-ie."
            akcja={<Przycisk onClick={nowy}><Plus className="size-4" /> Dodaj kontrahenta</Przycisk>}
          />
        ) : (
          <ul className={`divide-y divide-obramowanie transition-opacity ${lista.isPlaceholderData ? 'opacity-60' : ''}`}>
            {lista.data.pozycje.map((k) => <WierszKontrahenta key={k.id} k={k} onOtworz={() => setOtwarty({ id: k.id, dane: k })} />)}
          </ul>
        )}
        {lista.data && <Paginacja razem={lista.data.razem} offset={offset} onZmiana={setOffset} />}
      </section>

      {otwarty && <PanelKontrahenta otwarty={otwarty} onZamknij={() => setOtwarty(null)} />}
    </div>
  )
}

function WierszKontrahenta({ k, onOtworz }: { k: Kontrahent; onOtworz: () => void }) {
  const miejsce = [k.kod_pocztowy, k.miejscowosc].filter(Boolean).join(' ')
  return (
    <li>
      <button type="button" onClick={onOtworz} className="flex w-full items-center gap-3 px-5 py-3.5 text-left transition hover:bg-marka-50/60">
        <Awatar tekst={k.nazwa} wylaczony={!k.aktywny} />
        <div className={`min-w-0 flex-1 ${k.aktywny ? '' : 'opacity-60'}`}>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="truncate font-medium text-marka-950">{k.nazwa}</span>
            {k.typ === 'osoba_fizyczna' && <Plakietka><UserRound className="size-3" /> osoba</Plakietka>}
          </div>
          <div className="liczby mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-neutral-500">
            {k.nip && <span>NIP {k.nip}</span>}
            {miejsce && <span className="inline-flex items-center gap-1"><MapPin className="size-3" />{miejsce}</span>}
            {k.telefon && <span className="inline-flex items-center gap-1"><Phone className="size-3" />{k.telefon}</span>}
            {k.email && <span className="inline-flex items-center gap-1"><Mail className="size-3" />{k.email}</span>}
          </div>
        </div>
        <div className="hidden shrink-0 gap-1.5 sm:flex">
          {k.jest_odbiorca && <Plakietka ton="zielony">Odbiorca</Plakietka>}
          {k.jest_dostawca && <Plakietka ton="zloty">Dostawca</Plakietka>}
          {!k.aktywny && <Plakietka>Wyłączony</Plakietka>}
        </div>
      </button>
    </li>
  )
}

function PanelKontrahenta({ otwarty, onZamknij }: { otwarty: NonNullable<Otwarty>; onZamknij: () => void }) {
  const [dane, setDane] = useState<KontrahentDane>(otwarty.dane)
  const [biala, setBiala] = useState<{ laduje?: boolean; blad?: string; status?: string }>({})
  const zapisz = useZapiszKontrahenta()
  const nowy = otwarty.id === null
  const ustaw = <K extends keyof KontrahentDane>(pole: K, wartosc: KontrahentDane[K]) => setDane((d) => ({ ...d, [pole]: wartosc }))
  const tekst = (pole: 'nazwa' | 'nip' | 'nr_vat_ue' | 'regon' | 'adres_ulica' | 'kod_pocztowy' | 'miejscowosc' | 'kraj' | 'email' | 'telefon') =>
    ({ value: dane[pole], onChange: (e: { target: { value: string } }) => ustaw(pole, e.target.value) })

  const wyslij = (e: Pick<FormEvent, 'preventDefault'>, zmiana: Partial<KontrahentDane> = {}) => {
    e.preventDefault()
    zapisz.mutate({ id: otwarty.id, dane: { ...dane, ...zmiana } }, { onSuccess: onZamknij })
  }

  const zBialejListy = async () => {
    setBiala({ laduje: true })
    try {
      const p = await pobierzZBialejListy(dane.nip)
      setDane((d) => ({
        ...d, nip: p.nip, nazwa: p.nazwa || d.nazwa, regon: p.regon || d.regon, adres_ulica: p.adres_ulica || d.adres_ulica,
        kod_pocztowy: p.kod_pocztowy || d.kod_pocztowy, miejscowosc: p.miejscowosc || d.miejscowosc, kraj: 'PL', typ: 'firma',
      }))
      setBiala({ status: p.status_vat })
    } catch (err) {
      setBiala({ blad: (err as Error).message })
    }
  }

  return (
    <Panel
      tytul={nowy ? 'Nowy kontrahent' : otwarty.dane.nazwa}
      opis={nowy ? 'Wpisz NIP i pobierz dane z Białej Listy MF — resztę wypełni formularz.' : undefined}
      onZamknij={onZamknij}
      blad={zapisz.error?.message}
      stopka={
        <>
          <Przycisk type="submit" form="formularz-kontrahenta" laduje={zapisz.isPending}>{nowy ? 'Dodaj kontrahenta' : 'Zapisz zmiany'}</Przycisk>
          <Przycisk wariant="cichy" onClick={onZamknij}>Anuluj</Przycisk>
          {!nowy && (
            <Przycisk wariant="cichy" className="ml-auto" disabled={zapisz.isPending}
              onClick={(e) => wyslij(e, { aktywny: !dane.aktywny })}>
              {dane.aktywny ? 'Wyłącz kontrahenta' : 'Włącz ponownie'}
            </Przycisk>
          )}
        </>
      }
    >
      <form id="formularz-kontrahenta" onSubmit={wyslij}>
        <SekcjaFormularza tytul="Dane podstawowe">
          <Pole etykieta="Typ" className="sm:col-span-2">
            <Wybor value={dane.typ} onChange={(e) => ustaw('typ', e.target.value as KontrahentDane['typ'])}>
              <option value="firma">Firma</option>
              <option value="osoba_fizyczna">Osoba fizyczna</option>
            </Wybor>
          </Pole>
          <Pole etykieta="NIP" className="sm:col-span-4" podpowiedz="Biała Lista: limit 10 zapytań dziennie — używaj świadomie.">
            <div className="flex gap-2">
              <Wejscie {...tekst('nip')} placeholder="000-000-00-00" className="liczby font-mono" />
              <Przycisk wariant="drugorzedny" laduje={biala.laduje} disabled={!dane.nip.trim()} onClick={zBialejListy} title="Pobierz dane z Białej Listy MF">
                <Download className="size-4" /> Pobierz
              </Przycisk>
            </div>
          </Pole>
          {biala.status && (
            <div className="sm:col-span-6">
              <Komunikat rodzaj={biala.status === 'Czynny' ? 'sukces' : 'info'}>Dane pobrane z Białej Listy. Status VAT: <b>{biala.status}</b>.</Komunikat>
            </div>
          )}
          {biala.blad && <div className="sm:col-span-6"><Komunikat rodzaj="blad">{biala.blad}</Komunikat></div>}
          <Pole etykieta="Nazwa" className="sm:col-span-6"><Wejscie {...tekst('nazwa')} required /></Pole>
          <Pole etykieta="REGON" className="sm:col-span-3"><Wejscie {...tekst('regon')} className="liczby font-mono" /></Pole>
          <Pole etykieta="Nr VAT UE" className="sm:col-span-3" podpowiedz="Dla kontrahentów z UE, np. DE123456789"><Wejscie {...tekst('nr_vat_ue')} className="font-mono uppercase" /></Pole>
        </SekcjaFormularza>

        <SekcjaFormularza tytul="Adres">
          <Pole etykieta="Ulica i numer" className="sm:col-span-6"><Wejscie {...tekst('adres_ulica')} /></Pole>
          <Pole etykieta="Kod pocztowy" className="sm:col-span-2"><Wejscie {...tekst('kod_pocztowy')} placeholder="00-000" /></Pole>
          <Pole etykieta="Miejscowość" className="sm:col-span-3"><Wejscie {...tekst('miejscowosc')} /></Pole>
          <Pole etykieta="Kraj" className="sm:col-span-1"><Wejscie {...tekst('kraj')} maxLength={2} className="uppercase" /></Pole>
        </SekcjaFormularza>

        <SekcjaFormularza tytul="Kontakt">
          <Pole etykieta="E-mail" className="sm:col-span-3"><Wejscie type="email" {...tekst('email')} /></Pole>
          <Pole etykieta="Telefon" className="sm:col-span-3"><Wejscie type="tel" {...tekst('telefon')} /></Pole>
        </SekcjaFormularza>

        <SekcjaFormularza tytul="Handel">
          <div className="flex flex-wrap gap-x-6 gap-y-2 sm:col-span-6">
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={dane.jest_odbiorca} onChange={(e) => ustaw('jest_odbiorca', e.target.checked)} className="size-4 accent-marka-700" />
              Odbiorca (kupuje od nas)
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={dane.jest_dostawca} onChange={(e) => ustaw('jest_dostawca', e.target.checked)} className="size-4 accent-marka-700" />
              Dostawca (kupujemy od niego)
            </label>
          </div>
          <Pole etykieta="Termin płatności (dni)" className="sm:col-span-3" podpowiedz="Puste = termin domyślny z Ustawień → Firma">
            <Wejscie type="number" min={0} max={365} value={dane.termin_platnosci_dni ?? ''}
              onChange={(e) => ustaw('termin_platnosci_dni', e.target.value === '' ? null : Number(e.target.value))} />
          </Pole>
          <Pole etykieta="Uwagi" className="sm:col-span-6">
            <PoleTekstowe rows={3} value={dane.uwagi} onChange={(e) => ustaw('uwagi', e.target.value)} />
          </Pole>
        </SekcjaFormularza>

      </form>
    </Panel>
  )
}
