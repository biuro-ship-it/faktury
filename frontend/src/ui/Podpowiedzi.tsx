import { useQuery } from '@tanstack/react-query'
import { LoaderCircle } from 'lucide-react'
import { type KeyboardEvent, type ReactNode, useId, useState } from 'react'
import { useOpoznione } from './kartoteka'

/** Pole tekstowe z listą podpowiedzi z serwera (kontrahenci, towary). Wpisany tekst zostaje, nawet gdy
 *  nic nie wybierzesz — np. pozycja faktury spoza kartoteki. Strzałki + Enter wybierają, Esc zamyka listę. */
export function Podpowiedzi<T extends { id: number }>({
  klucz, wartosc, onZmiana, onWybierz, szukaj, pokaz, placeholder, className = '', etykieta, wymagane,
}: {
  klucz: string
  wartosc: string
  onZmiana: (tekst: string) => void
  onWybierz: (element: T) => void
  szukaj: (q: string) => Promise<T[]>
  pokaz: (element: T) => ReactNode
  placeholder?: string
  className?: string
  etykieta: string
  wymagane?: boolean
}) {
  const id = useId()
  const [otwarte, setOtwarte] = useState(false)
  const [aktywny, setAktywny] = useState(0)
  const q = useOpoznione(wartosc, 200)
  const wyniki = useQuery({ queryKey: ['podpowiedzi', klucz, q], queryFn: () => szukaj(q), enabled: otwarte, staleTime: 30_000 })
  const lista = wyniki.data ?? []

  const wybierz = (e: T) => {
    onWybierz(e)
    setOtwarte(false)
  }
  const naKlawisz = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOtwarte(true); setAktywny((a) => Math.min(a + 1, lista.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setAktywny((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter' && otwarte && lista[aktywny]) { e.preventDefault(); wybierz(lista[aktywny]) }
    else if (e.key === 'Escape' && otwarte) { e.stopPropagation(); setOtwarte(false) } // nie zamykaj całego okna
  }

  return (
    <div className="relative">
      <input
        value={wartosc}
        onChange={(e) => { onZmiana(e.target.value); setOtwarte(true); setAktywny(0) }}
        onFocus={() => setOtwarte(true)}
        onBlur={() => setOtwarte(false)}
        onKeyDown={naKlawisz}
        placeholder={placeholder}
        aria-label={etykieta}
        required={wymagane}
        role="combobox"
        aria-expanded={otwarte && lista.length > 0}
        aria-controls={id}
        aria-autocomplete="list"
        autoComplete="off"
        className={`block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm placeholder:text-neutral-400 focus:border-marka-500 focus:outline-none focus:ring-2 focus:ring-marka-200 ${className}`}
      />
      {otwarte && (wyniki.isFetching || lista.length > 0) && (
        <ul id={id} role="listbox" className="absolute left-0 top-full z-50 mt-1 max-h-64 w-full min-w-72 overflow-y-auto rounded-lg border border-obramowanie bg-white py-1 shadow-lg">
          {lista.length === 0 && (
            <li className="flex items-center gap-2 px-3 py-2 text-sm text-neutral-500"><LoaderCircle className="size-4 animate-spin" /> Szukam…</li>
          )}
          {lista.map((e, i) => (
            <li
              key={e.id}
              role="option"
              aria-selected={i === aktywny}
              // mousedown, nie click — inaczej blur zamknie listę, zanim wybór dojdzie
              onMouseDown={(ev) => { ev.preventDefault(); wybierz(e) }}
              onMouseEnter={() => setAktywny(i)}
              className={`cursor-pointer px-3 py-2 text-sm ${i === aktywny ? 'bg-marka-50 text-marka-950' : 'text-tekst'}`}
            >
              {pokaz(e)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
