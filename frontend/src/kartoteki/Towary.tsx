import { Boxes, FlaskConical, Package, PackageCheck, Plus, Wrench } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Komunikat, Pole, Przycisk, PoleTekstowe, Wejscie, Wybor } from '../ui/formularz'
import {
  NA_STRONE, Paginacja, Panel, Plakietka, Segmenty, SekcjaFormularza, Szukajka, StanPusty, SzkieletWierszy, useOpoznione,
} from '../ui/kartoteka'
import { useStawki } from '../ustawienia/api'
import {
  type Aktywnosc, JEDNOSTKI, KODY_GTU, naGrosze, naZlote, PUSTY_TOWAR, type TowarDane, TYPY_TOWARU,
  type TypTowaru, useTowary, useZapiszTowar,
} from './api'

const AKTYWNOSC = [
  { wartosc: 'tak', nazwa: 'Aktywne' },
  { wartosc: 'nie', nazwa: 'Wyłączone' },
  { wartosc: 'wszystkie', nazwa: 'Wszystkie' },
] as const

const TYPY: { wartosc: TypTowaru | 'wszystkie'; nazwa: string }[] = [
  { wartosc: 'wszystkie', nazwa: 'Wszystkie' },
  { wartosc: 'towar_handlowy', nazwa: 'Towary' },
  { wartosc: 'surowiec', nazwa: 'Surowce' },
  { wartosc: 'wyrob_gotowy', nazwa: 'Wyroby' },
  { wartosc: 'usluga', nazwa: 'Usługi' },
]

const IKONY: Record<TypTowaru, ReactNode> = {
  towar_handlowy: <Package className="size-4" />,
  surowiec: <FlaskConical className="size-4" />,
  wyrob_gotowy: <PackageCheck className="size-4" />,
  usluga: <Wrench className="size-4" />,
}
const TONY: Record<TypTowaru, 'zielony' | 'zloty' | 'niebieski' | 'szary'> = {
  towar_handlowy: 'zielony', surowiec: 'zloty', wyrob_gotowy: 'niebieski', usluga: 'szary',
}

type Otwarty = { id: number | null; dane: TowarDane; nazwa: string } | null

export function Towary() {
  const [q, setQ] = useState('')
  const [aktywnosc, setAktywnosc] = useState<Aktywnosc>('tak')
  const [typ, setTyp] = useState<TypTowaru | 'wszystkie'>('wszystkie')
  const [offset, setOffset] = useState(0)
  const [otwarty, setOtwarty] = useState<Otwarty>(null)
  const szukane = useOpoznione(q)
  const lista = useTowary({ q: szukane, aktywnosc, offset, limit: NA_STRONE }, typ)
  const filtrowane = szukane.trim() !== '' || aktywnosc !== 'tak' || typ !== 'wszystkie'
  const nowy = () => setOtwarty({ id: null, dane: { ...PUSTY_TOWAR, typ: typ === 'wszystkie' ? 'towar_handlowy' : typ, jm: typ === 'usluga' ? 'usł.' : 'szt.' }, nazwa: '' })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Szukajka wartosc={q} onZmiana={(v) => { setQ(v); setOffset(0) }} placeholder="Szukaj po symbolu, nazwie, EAN…" />
        <Segmenty etykieta="Rodzaj" opcje={TYPY} wartosc={typ} onZmiana={(v) => { setTyp(v); setOffset(0) }} />
        <Segmenty etykieta="Status" opcje={[...AKTYWNOSC]} wartosc={aktywnosc} onZmiana={(v) => { setAktywnosc(v); setOffset(0) }} />
        <Przycisk className="ml-auto" onClick={nowy}><Plus className="size-4" /> Nowa pozycja</Przycisk>
      </div>

      <section className="overflow-hidden rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
        {lista.isPending ? (
          <SzkieletWierszy />
        ) : lista.isError ? (
          <div className="p-5"><Komunikat rodzaj="blad">{lista.error.message}</Komunikat></div>
        ) : lista.data.pozycje.length === 0 ? (
          <StanPusty
            filtrowane={filtrowane} ikona={<Boxes className="size-6" />} tytul="Brak pozycji w kartotece"
            opis="Dodaj towary handlowe, surowce do produkcji, wyroby gotowe i usługi — z nich powstaną faktury i magazyn."
            akcja={<Przycisk onClick={nowy}><Plus className="size-4" /> Dodaj pozycję</Przycisk>}
          />
        ) : (
          <div className={`overflow-x-auto transition-opacity ${lista.isPlaceholderData ? 'opacity-60' : ''}`}>
            <table className="w-full min-w-176 text-sm">
              <thead>
                <tr className="border-b border-obramowanie bg-neutral-50/70 text-left text-xs uppercase tracking-wider text-neutral-500">
                  <th className="px-5 py-2.5 font-medium">Symbol</th>
                  <th className="py-2.5 pr-4 font-medium">Nazwa</th>
                  <th className="py-2.5 pr-4 font-medium">Rodzaj</th>
                  <th className="py-2.5 pr-4 text-right font-medium">VAT</th>
                  <th className="px-5 py-2.5 text-right font-medium">Cena netto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-obramowanie">
                {lista.data.pozycje.map((t) => (
                  <tr key={t.id} onClick={() => setOtwarty({ id: t.id, dane: t, nazwa: t.nazwa })} className={`cursor-pointer transition hover:bg-marka-50/60 ${t.aktywny ? '' : 'text-neutral-400'}`}>
                    <td className="px-5 py-3 font-mono text-xs">
                      <button type="button" className="text-left font-medium text-marka-900 hover:underline focus-visible:underline" onClick={(e) => { e.stopPropagation(); setOtwarty({ id: t.id, dane: t, nazwa: t.nazwa }) }}>{t.symbol}</button>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="font-medium">{t.nazwa}</span>
                      {!t.aktywny && <span className="ml-2"><Plakietka>Wyłączony</Plakietka></span>}
                    </td>
                    <td className="py-3 pr-4"><Plakietka ton={TONY[t.typ]}>{IKONY[t.typ]}{TYPY_TOWARU[t.typ]}</Plakietka></td>
                    <td className="liczby py-3 pr-4 text-right">{t.stawka_vat_kod === 'zw' || t.stawka_vat_kod.startsWith('np') || t.stawka_vat_kod === 'oo' ? t.stawka_vat_kod : `${t.stawka_vat_kod}%`}</td>
                    <td className="liczby px-5 py-3 text-right">
                      {t.cena_sprzedazy_netto === null ? <span className="text-neutral-400">—</span> : <>{naZlote(t.cena_sprzedazy_netto)} <span className="text-xs text-neutral-500">zł/{t.jm}</span></>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {lista.data && <Paginacja razem={lista.data.razem} offset={offset} onZmiana={setOffset} />}
      </section>

      {otwarty && <PanelTowaru otwarty={otwarty} onZamknij={() => setOtwarty(null)} />}
    </div>
  )
}

function PanelTowaru({ otwarty, onZamknij }: { otwarty: NonNullable<Otwarty>; onZamknij: () => void }) {
  const [dane, setDane] = useState<TowarDane>(otwarty.dane)
  const [cena, setCena] = useState(naZlote(otwarty.dane.cena_sprzedazy_netto))
  const [blad, setBlad] = useState<string | null>(null)
  const stawki = useStawki()
  const zapisz = useZapiszTowar()
  const nowy = otwarty.id === null
  const ustaw = <K extends keyof TowarDane>(pole: K, wartosc: TowarDane[K]) => setDane((d) => ({ ...d, [pole]: wartosc }))

  // Do wyboru: stawki aktywne + ta, którą towar już ma (nawet gdy później ją wyłączono).
  const dostepne = (stawki.data ?? []).filter((s) => s.aktywna || s.kod === otwarty.dane.stawka_vat_kod)
  const stawka = dane.stawka_vat_kod || stawki.data?.find((s) => s.domyslna)?.kod || ''

  const wyslij = (e: Pick<FormEvent, 'preventDefault'>, zmiana: Partial<TowarDane> = {}) => {
    e.preventDefault()
    const grosze = naGrosze(cena)
    if (grosze === undefined) return setBlad('Cena: wpisz kwotę, np. 12,50')
    if (!stawka) return setBlad('Wybierz stawkę VAT')
    setBlad(null)
    zapisz.mutate({ id: otwarty.id, dane: { ...dane, stawka_vat_kod: stawka, cena_sprzedazy_netto: grosze, ...zmiana } }, { onSuccess: onZamknij })
  }

  return (
    <Panel
      tytul={nowy ? 'Nowa pozycja' : otwarty.nazwa}
      opis={nowy ? 'Towar, surowiec, wyrób gotowy albo usługa.' : `Symbol ${otwarty.dane.symbol}`}
      onZamknij={onZamknij}
      blad={blad ?? zapisz.error?.message}
      stopka={
        <>
          <Przycisk type="submit" form="formularz-towaru" laduje={zapisz.isPending}>{nowy ? 'Dodaj pozycję' : 'Zapisz zmiany'}</Przycisk>
          <Przycisk wariant="cichy" onClick={onZamknij}>Anuluj</Przycisk>
          {!nowy && (
            <Przycisk wariant="cichy" className="ml-auto" disabled={zapisz.isPending} onClick={(e) => wyslij(e, { aktywny: !dane.aktywny })}>
              {dane.aktywny ? 'Wyłącz pozycję' : 'Włącz ponownie'}
            </Przycisk>
          )}
        </>
      }
    >
      <form id="formularz-towaru" onSubmit={wyslij}>
        <SekcjaFormularza tytul="Identyfikacja">
          <Pole etykieta="Rodzaj" className="sm:col-span-6">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(Object.keys(TYPY_TOWARU) as TypTowaru[]).map((t) => (
                <button
                  key={t} type="button" aria-pressed={dane.typ === t} onClick={() => ustaw('typ', t)}
                  className={`flex flex-col items-center gap-1.5 rounded-lg border px-2 py-3 text-xs font-medium transition ${
                    dane.typ === t ? 'border-marka-600 bg-marka-50 text-marka-900 ring-1 ring-marka-600' : 'border-neutral-200 text-neutral-600 hover:border-marka-300 hover:bg-marka-50/50'
                  }`}
                >
                  {IKONY[t]}{TYPY_TOWARU[t]}
                </button>
              ))}
            </div>
          </Pole>
          <Pole etykieta="Symbol" className="sm:col-span-2" podpowiedz="Wielkie litery, cyfry, . _ / -">
            <Wejscie value={dane.symbol} onChange={(e) => ustaw('symbol', e.target.value.toUpperCase())} required className="font-mono" />
          </Pole>
          <Pole etykieta="Nazwa" className="sm:col-span-4">
            <Wejscie value={dane.nazwa} onChange={(e) => ustaw('nazwa', e.target.value)} required />
          </Pole>
          <Pole etykieta="EAN" className="sm:col-span-3"><Wejscie value={dane.ean} onChange={(e) => ustaw('ean', e.target.value)} inputMode="numeric" className="liczby font-mono" /></Pole>
        </SekcjaFormularza>

        <SekcjaFormularza tytul="Sprzedaż i podatki">
          <Pole etykieta="Jednostka miary" className="sm:col-span-3">
            <Wejscie list="jednostki" value={dane.jm} onChange={(e) => ustaw('jm', e.target.value)} required maxLength={10} />
            <datalist id="jednostki">{JEDNOSTKI.map((j) => <option key={j} value={j} />)}</datalist>
          </Pole>
          <Pole etykieta="Cena sprzedaży netto" className="sm:col-span-3" podpowiedz="Zł za jednostkę">
            <Wejscie value={cena} onChange={(e) => setCena(e.target.value)} inputMode="decimal" placeholder="0,00" className="liczby text-right" />
          </Pole>
          <Pole etykieta="Stawka VAT" className="sm:col-span-3">
            <Wybor value={stawka} onChange={(e) => ustaw('stawka_vat_kod', e.target.value)} required>
              {dostepne.map((s) => <option key={s.kod} value={s.kod}>{s.nazwa}</option>)}
            </Wybor>
          </Pole>
          <Pole etykieta="GTU" className="sm:col-span-3" podpowiedz="Oznaczenie towarów i usług w JPK_V7 — zwykle puste">
            <Wybor value={dane.gtu ?? ''} onChange={(e) => ustaw('gtu', e.target.value || null)}>
              <option value="">— brak —</option>
              {KODY_GTU.map((g) => <option key={g} value={g}>{g}</option>)}
            </Wybor>
          </Pole>
          <Pole etykieta="Uwagi" className="sm:col-span-6"><PoleTekstowe rows={3} value={dane.uwagi} onChange={(e) => ustaw('uwagi', e.target.value)} /></Pole>
        </SekcjaFormularza>

        {dane.typ === 'usluga' && <p className="mb-4 text-sm text-tekst-drugorzedny">Usługi nie wchodzą na magazyn.</p>}
      </form>
    </Panel>
  )
}
