import { FileText, Plus } from 'lucide-react'
import { useState } from 'react'
import { naZlote } from '../kartoteki/api'
import { Komunikat, Przycisk, Wejscie } from '../ui/formularz'
import { NA_STRONE, Paginacja, Plakietka, Segmenty, StanPusty, Szukajka, SzkieletWierszy, useOpoznione } from '../ui/kartoteka'
import { type FiltrStatusu, granicaMiesiaca, naDate, STATUSY, useFaktury } from './api'
import { FakturaOkno, TON_STATUSU } from './FakturaOkno'

const FILTRY_STATUSU: { wartosc: FiltrStatusu; nazwa: string }[] = [
  { wartosc: 'wszystkie', nazwa: 'Wszystkie' },
  { wartosc: 'szkic', nazwa: 'Szkice' },
  { wartosc: 'zatwierdzony', nazwa: 'Zatwierdzone' },
  { wartosc: 'anulowany', nazwa: 'Anulowane' },
]

type Otwarta = { id: number | null } | null

export function Faktury() {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<FiltrStatusu>('wszystkie')
  const [miesiac, setMiesiac] = useState('')
  const [offset, setOffset] = useState(0)
  const [otwarta, setOtwarta] = useState<Otwarta>(null)
  const szukane = useOpoznione(q)
  const okres = miesiac ? granicaMiesiaca(miesiac) : {}
  const lista = useFaktury({ q: szukane, status, ...okres, offset, limit: NA_STRONE })
  const filtrowane = szukane.trim() !== '' || status !== 'wszystkie' || miesiac !== ''
  const nowa = () => setOtwarta({ id: null })
  const przewin = <T,>(f: (v: T) => void) => (v: T) => { f(v); setOffset(0) }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Szukajka wartosc={q} onZmiana={przewin(setQ)} placeholder="Szukaj po numerze, nabywcy, NIP…" />
        <div className="max-w-full overflow-x-auto">
          <Segmenty etykieta="Status" opcje={FILTRY_STATUSU} wartosc={status} onZmiana={przewin(setStatus)} />
        </div>
        <Wejscie type="month" aria-label="Miesiąc wystawienia" value={miesiac} onChange={(e) => przewin(setMiesiac)(e.target.value)} className="!w-auto" />
        <Przycisk className="ml-auto" onClick={nowa}><Plus className="size-4" /> Nowa faktura</Przycisk>
      </div>

      <section className="overflow-hidden rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
        {lista.isPending ? (
          <SzkieletWierszy />
        ) : lista.isError ? (
          <div className="p-5"><Komunikat rodzaj="blad">{lista.error.message}</Komunikat></div>
        ) : lista.data.pozycje.length === 0 ? (
          <StanPusty
            filtrowane={filtrowane} ikona={<FileText className="size-6" />} tytul="Nie ma jeszcze faktur"
            opis="Wystaw pierwszą fakturę — zapisz ją jako szkic, a po sprawdzeniu zatwierdź, żeby nadać numer."
            akcja={<Przycisk onClick={nowa}><Plus className="size-4" /> Nowa faktura</Przycisk>}
          />
        ) : (
          <div className={`overflow-x-auto transition-opacity ${lista.isPlaceholderData ? 'opacity-60' : ''}`}>
            <table className="w-full min-w-200 text-sm">
              <thead>
                <tr className="border-b border-obramowanie bg-neutral-50/70 text-left text-xs uppercase tracking-wider text-neutral-500">
                  <th className="px-5 py-2.5 font-medium">Numer</th>
                  <th className="py-2.5 pr-4 font-medium">Nabywca</th>
                  <th className="py-2.5 pr-4 font-medium">Wystawiona</th>
                  <th className="py-2.5 pr-4 font-medium">Termin</th>
                  <th className="py-2.5 pr-4 text-right font-medium">Netto</th>
                  <th className="px-5 py-2.5 text-right font-medium">Brutto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-obramowanie">
                {lista.data.pozycje.map((f) => (
                  <tr key={f.id} onClick={() => setOtwarta({ id: f.id })} className={`cursor-pointer transition hover:bg-marka-50/60 ${f.status === 'anulowany' ? 'text-neutral-400' : ''}`}>
                    <td className="px-5 py-3">
                      <button type="button" onClick={(e) => { e.stopPropagation(); setOtwarta({ id: f.id }) }}
                        className={`liczby text-left font-medium hover:underline focus-visible:underline ${f.status === 'anulowany' ? 'line-through' : 'text-marka-900'}`}>
                        {f.numer ?? <span className="italic text-neutral-500">bez numeru</span>}
                      </button>
                      {f.status !== 'zatwierdzony' && <span className="ml-2"><Plakietka ton={TON_STATUSU[f.status]}>{STATUSY[f.status]}</Plakietka></span>}
                    </td>
                    <td className="py-3 pr-4">
                      <span className="block font-medium">{f.nabywca_nazwa || <span className="text-neutral-400">—</span>}</span>
                      {f.nabywca_nip && <span className="liczby text-xs text-neutral-500">NIP {f.nabywca_nip}</span>}
                    </td>
                    <td className="liczby py-3 pr-4">{naDate(f.data_wystawienia)}</td>
                    <td className="liczby py-3 pr-4">{naDate(f.termin_platnosci)}</td>
                    <td className="liczby py-3 pr-4 text-right">{naZlote(f.suma_netto)}</td>
                    <td className="liczby px-5 py-3 text-right font-semibold">{naZlote(f.suma_brutto)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-obramowanie bg-marka-50/40 text-sm">
                  <td colSpan={4} className="px-5 py-2.5 text-xs text-tekst-drugorzedny">Suma zatwierdzonych faktur z filtra (bez szkiców i anulowanych)</td>
                  <td className="liczby py-2.5 pr-4 text-right font-medium">{naZlote(lista.data.suma_netto)}</td>
                  <td className="liczby px-5 py-2.5 text-right font-semibold text-marka-950">{naZlote(lista.data.suma_brutto)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
        {lista.data && <Paginacja razem={lista.data.razem} offset={offset} onZmiana={setOffset} />}
      </section>

      {otwarta && <FakturaOkno id={otwarta.id} onZamknij={() => setOtwarta(null)} />}
    </div>
  )
}
