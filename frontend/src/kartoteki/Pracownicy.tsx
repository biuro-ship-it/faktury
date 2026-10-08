import { Mail, Phone, Plus, UsersRound } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Komunikat, Pole, Przycisk, PoleTekstowe, Wejscie } from '../ui/formularz'
import {
  Awatar, NA_STRONE, Paginacja, Panel, Plakietka, Segmenty, SekcjaFormularza, Szukajka, StanPusty, SzkieletWierszy, useOpoznione,
} from '../ui/kartoteka'
import { type Aktywnosc, PUSTY_PRACOWNIK, type Pracownik, type PracownikDane, usePracownicy, useZapiszPracownika } from './api'

const AKTYWNOSC = [
  { wartosc: 'tak', nazwa: 'Zatrudnieni' },
  { wartosc: 'nie', nazwa: 'Wyłączeni' },
  { wartosc: 'wszystkie', nazwa: 'Wszyscy' },
] as const

type Otwarty = { id: number | null; dane: PracownikDane; nazwa: string } | null

const dataPL = (iso: string | null) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('pl-PL') : '')

export function Pracownicy() {
  const [q, setQ] = useState('')
  const [aktywnosc, setAktywnosc] = useState<Aktywnosc>('tak')
  const [offset, setOffset] = useState(0)
  const [otwarty, setOtwarty] = useState<Otwarty>(null)
  const szukane = useOpoznione(q)
  const lista = usePracownicy({ q: szukane, aktywnosc, offset, limit: NA_STRONE })
  const filtrowane = szukane.trim() !== '' || aktywnosc !== 'tak'
  const nowy = () => setOtwarty({ id: null, dane: PUSTY_PRACOWNIK, nazwa: '' })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Szukajka wartosc={q} onZmiana={(v) => { setQ(v); setOffset(0) }} placeholder="Szukaj po nazwisku, stanowisku…" />
        <Segmenty etykieta="Status" opcje={[...AKTYWNOSC]} wartosc={aktywnosc} onZmiana={(v) => { setAktywnosc(v); setOffset(0) }} />
        <Przycisk className="ml-auto" onClick={nowy}><Plus className="size-4" /> Nowy pracownik</Przycisk>
      </div>

      <section className="overflow-hidden rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
        {lista.isPending ? (
          <SzkieletWierszy />
        ) : lista.isError ? (
          <div className="p-5"><Komunikat rodzaj="blad">{lista.error.message}</Komunikat></div>
        ) : lista.data.pozycje.length === 0 ? (
          <StanPusty
            filtrowane={filtrowane} ikona={<UsersRound className="size-6" />} tytul="Brak pracowników"
            opis="Kartoteka pracowników przyda się przy zleceniach produkcyjnych i kasie. Bez PESEL-u i wynagrodzeń."
            akcja={<Przycisk onClick={nowy}><Plus className="size-4" /> Dodaj pracownika</Przycisk>}
          />
        ) : (
          <ul className={`divide-y divide-obramowanie transition-opacity ${lista.isPlaceholderData ? 'opacity-60' : ''}`}>
            {lista.data.pozycje.map((p) => <WierszPracownika key={p.id} p={p} onOtworz={() => setOtwarty({ id: p.id, dane: p, nazwa: `${p.imie} ${p.nazwisko}` })} />)}
          </ul>
        )}
        {lista.data && <Paginacja razem={lista.data.razem} offset={offset} onZmiana={setOffset} />}
      </section>

      {otwarty && <PanelPracownika otwarty={otwarty} onZamknij={() => setOtwarty(null)} />}
    </div>
  )
}

function WierszPracownika({ p, onOtworz }: { p: Pracownik; onOtworz: () => void }) {
  return (
    <li>
      <button type="button" onClick={onOtworz} className="flex w-full items-center gap-3 px-5 py-3.5 text-left transition hover:bg-marka-50/60">
        <Awatar tekst={`${p.imie} ${p.nazwisko}`} wylaczony={!p.aktywny} />
        <div className={`min-w-0 flex-1 ${p.aktywny ? '' : 'opacity-60'}`}>
          <div className="font-medium text-marka-950">{p.nazwisko} {p.imie}</div>
          <div className="liczby mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-neutral-500">
            {p.stanowisko && <span>{p.stanowisko}</span>}
            {p.telefon && <span className="inline-flex items-center gap-1"><Phone className="size-3" />{p.telefon}</span>}
            {p.email && <span className="inline-flex items-center gap-1"><Mail className="size-3" />{p.email}</span>}
          </div>
        </div>
        <div className="hidden shrink-0 text-right text-xs text-neutral-500 sm:block">
          {p.aktywny ? (p.data_zatrudnienia && <>od {dataPL(p.data_zatrudnienia)}</>) : <Plakietka>Wyłączony{p.data_zwolnienia && ` ${dataPL(p.data_zwolnienia)}`}</Plakietka>}
        </div>
      </button>
    </li>
  )
}

function PanelPracownika({ otwarty, onZamknij }: { otwarty: NonNullable<Otwarty>; onZamknij: () => void }) {
  const [dane, setDane] = useState<PracownikDane>(otwarty.dane)
  const zapisz = useZapiszPracownika()
  const nowy = otwarty.id === null
  const ustaw = <K extends keyof PracownikDane>(pole: K, wartosc: PracownikDane[K]) => setDane((d) => ({ ...d, [pole]: wartosc }))
  const tekst = (pole: 'imie' | 'nazwisko' | 'stanowisko' | 'email' | 'telefon') =>
    ({ value: dane[pole], onChange: (e: { target: { value: string } }) => ustaw(pole, e.target.value) })

  const wyslij = (e: Pick<FormEvent, 'preventDefault'>, zmiana: Partial<PracownikDane> = {}) => {
    e.preventDefault()
    zapisz.mutate({ id: otwarty.id, dane: { ...dane, ...zmiana } }, { onSuccess: onZamknij })
  }

  return (
    <Panel
      tytul={nowy ? 'Nowy pracownik' : otwarty.nazwa}
      onZamknij={onZamknij}
      blad={zapisz.error?.message}
      stopka={
        <>
          <Przycisk type="submit" form="formularz-pracownika" laduje={zapisz.isPending}>{nowy ? 'Dodaj pracownika' : 'Zapisz zmiany'}</Przycisk>
          <Przycisk wariant="cichy" onClick={onZamknij}>Anuluj</Przycisk>
          {!nowy && (
            <Przycisk wariant="cichy" className="ml-auto" disabled={zapisz.isPending} onClick={(e) => wyslij(e, { aktywny: !dane.aktywny })}>
              {dane.aktywny ? 'Wyłącz pracownika' : 'Włącz ponownie'}
            </Przycisk>
          )}
        </>
      }
    >
      <form id="formularz-pracownika" onSubmit={wyslij}>
        <SekcjaFormularza tytul="Dane">
          <Pole etykieta="Imię" className="sm:col-span-3"><Wejscie {...tekst('imie')} required /></Pole>
          <Pole etykieta="Nazwisko" className="sm:col-span-3"><Wejscie {...tekst('nazwisko')} required /></Pole>
          <Pole etykieta="Stanowisko" className="sm:col-span-6"><Wejscie {...tekst('stanowisko')} /></Pole>
          <Pole etykieta="E-mail" className="sm:col-span-3"><Wejscie type="email" {...tekst('email')} /></Pole>
          <Pole etykieta="Telefon" className="sm:col-span-3"><Wejscie type="tel" {...tekst('telefon')} /></Pole>
        </SekcjaFormularza>
        <SekcjaFormularza tytul="Zatrudnienie">
          <Pole etykieta="Data zatrudnienia" className="sm:col-span-3">
            <Wejscie type="date" value={dane.data_zatrudnienia ?? ''} onChange={(e) => ustaw('data_zatrudnienia', e.target.value || null)} />
          </Pole>
          <Pole etykieta="Data zwolnienia" className="sm:col-span-3">
            <Wejscie type="date" value={dane.data_zwolnienia ?? ''} onChange={(e) => ustaw('data_zwolnienia', e.target.value || null)} />
          </Pole>
          <Pole etykieta="Uwagi" className="sm:col-span-6"><PoleTekstowe rows={3} value={dane.uwagi} onChange={(e) => ustaw('uwagi', e.target.value)} /></Pole>
        </SekcjaFormularza>
      </form>
    </Panel>
  )
}
