import { ChevronLeft, ChevronRight, GripHorizontal, Search, SearchX, X } from 'lucide-react'
import { type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from 'react'
import { Przycisk } from './formularz'

/** Wartość z opóźnieniem — szukajka nie odpytuje serwera po każdej literze. */
export function useOpoznione<T>(wartosc: T, ms = 300): T {
  const [opoznione, setOpoznione] = useState(wartosc)
  useEffect(() => {
    const t = setTimeout(() => setOpoznione(wartosc), ms)
    return () => clearTimeout(t)
  }, [wartosc, ms])
  return opoznione
}

export function Szukajka({ wartosc, onZmiana, placeholder }: { wartosc: string; onZmiana: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative min-w-60 flex-1 sm:max-w-sm">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-neutral-400" />
      <input
        type="search"
        value={wartosc}
        onChange={(e) => onZmiana(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="block w-full rounded-lg border border-neutral-300 bg-white py-2 pl-9 pr-3 text-sm placeholder:text-neutral-400 focus:border-marka-500 focus:outline-none focus:ring-2 focus:ring-marka-200"
      />
    </div>
  )
}

/** Przełącznik widoków w stylu „segmented control” — filtry, które zawsze widać. */
export function Segmenty<T extends string>({ opcje, wartosc, onZmiana, etykieta }: {
  opcje: { wartosc: T; nazwa: string }[]
  wartosc: T
  onZmiana: (v: T) => void
  etykieta: string
}) {
  return (
    <div role="radiogroup" aria-label={etykieta} className="inline-flex rounded-lg bg-neutral-100 p-0.5">
      {opcje.map((o) => (
        <button
          key={o.wartosc}
          type="button"
          role="radio"
          aria-checked={o.wartosc === wartosc}
          onClick={() => onZmiana(o.wartosc)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            o.wartosc === wartosc ? 'bg-white text-marka-950 shadow-sm' : 'text-neutral-600 hover:text-marka-900'
          }`}
        >
          {o.nazwa}
        </button>
      ))}
    </div>
  )
}

const TONY = {
  zielony: 'bg-marka-50 text-marka-800 ring-marka-200',
  zloty: 'bg-zloto-50 text-zloto-800 ring-zloto-200',
  szary: 'bg-neutral-100 text-neutral-600 ring-neutral-200',
  niebieski: 'bg-info-tlo text-info ring-info/20',
  pomaranczowy: 'bg-ostrzezenie-tlo text-ostrzezenie ring-ostrzezenie/20',
} as const

export function Plakietka({ ton = 'szary', children }: { ton?: keyof typeof TONY; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${TONY[ton]}`}>
      {children}
    </span>
  )
}

/** Kółko z inicjałami — rozpoznawalne w długiej liście, bez ładowania zdjęć. */
export function Awatar({ tekst, wylaczony = false }: { tekst: string; wylaczony?: boolean }) {
  const inicjaly = tekst.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join('')
  return (
    <span
      aria-hidden
      className={`grid size-9 shrink-0 place-items-center rounded-full text-xs font-semibold ${
        wylaczony ? 'bg-neutral-100 text-neutral-400' : 'bg-marka-100 text-marka-800'
      }`}
    >
      {inicjaly || '?'}
    </span>
  )
}

export function StanPusty({ filtrowane, ikona, tytul, opis, akcja }: {
  filtrowane: boolean
  ikona: ReactNode
  tytul: string
  opis: string
  akcja?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="grid size-12 place-items-center rounded-full bg-marka-50 text-marka-700">
        {filtrowane ? <SearchX className="size-6" /> : ikona}
      </div>
      <h3 className="mt-4 font-semibold text-marka-950">{filtrowane ? 'Brak wyników' : tytul}</h3>
      <p className="mt-1 max-w-sm text-sm text-tekst-drugorzedny">
        {filtrowane ? 'Zmień wyszukiwaną frazę albo filtry.' : opis}
      </p>
      {!filtrowane && akcja && <div className="mt-5">{akcja}</div>}
    </div>
  )
}

export function SzkieletWierszy({ ile = 6 }: { ile?: number }) {
  return (
    <ul aria-busy aria-label="Ładowanie" className="divide-y divide-obramowanie">
      {Array.from({ length: ile }, (_, i) => (
        <li key={i} className="flex items-center gap-3 px-5 py-3.5">
          <span className="size-9 animate-pulse rounded-full bg-neutral-100" />
          <span className="h-4 w-1/3 animate-pulse rounded bg-neutral-100" />
          <span className="ml-auto h-4 w-1/6 animate-pulse rounded bg-neutral-100" />
        </li>
      ))}
    </ul>
  )
}

export const NA_STRONE = 25

export function Paginacja({ razem, offset, onZmiana }: { razem: number; offset: number; onZmiana: (offset: number) => void }) {
  if (razem === 0) return null
  const od = offset + 1
  const do_ = Math.min(offset + NA_STRONE, razem)
  return (
    <div className="flex items-center justify-between gap-3 border-t border-obramowanie px-5 py-3 text-sm text-tekst-drugorzedny">
      <span className="liczby">{od}–{do_} z {razem}</span>
      <div className="flex gap-1">
        <Przycisk wariant="cichy" aria-label="Poprzednia strona" disabled={offset === 0} onClick={() => onZmiana(Math.max(0, offset - NA_STRONE))} className="!px-2">
          <ChevronLeft className="size-4" />
        </Przycisk>
        <Przycisk wariant="cichy" aria-label="Następna strona" disabled={do_ >= razem} onClick={() => onZmiana(offset + NA_STRONE)} className="!px-2">
          <ChevronRight className="size-4" />
        </Przycisk>
      </div>
    </div>
  )
}

/** Okno na środku ekranu: formularz bez opuszczania listy. Przesuwasz je za nagłówek;
 *  Esc i kliknięcie w tło zamykają. */
export function Panel({ tytul, opis, blad, onZamknij, children, stopka }: {
  tytul: string
  opis?: string
  /** Błąd zapisu — przypięty pod nagłówkiem, żeby był widoczny także przy długim, przewiniętym formularzu. */
  blad?: string | null
  onZamknij: () => void
  children: ReactNode
  stopka?: ReactNode
}) {
  const okno = useRef<HTMLElement>(null)
  const [przesuniecie, setPrzesuniecie] = useState({ x: 0, y: 0 })
  const [przeciaga, setPrzeciaga] = useState(false)
  const start = useRef<{ x: number; y: number; baza: { x: number; y: number }; prostokat: DOMRect } | null>(null)

  useEffect(() => {
    const poprzedni = document.activeElement as HTMLElement | null
    const naKlawisz = (e: KeyboardEvent) => e.key === 'Escape' && onZamknij()
    document.addEventListener('keydown', naKlawisz)
    const przewijanie = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    okno.current?.querySelector<HTMLElement>('input:not([type=checkbox]):not([type=radio]), textarea, select')?.focus()
    return () => {
      document.removeEventListener('keydown', naKlawisz)
      document.body.style.overflow = przewijanie
      poprzedni?.focus()
    }
  }, [onZamknij])

  const zacznij = (e: ReactPointerEvent<HTMLElement>) => {
    if (e.button !== 0 || (e.target as HTMLElement).closest('button') || !okno.current) return
    e.currentTarget.setPointerCapture(e.pointerId)
    start.current = { x: e.clientX, y: e.clientY, baza: przesuniecie, prostokat: okno.current.getBoundingClientRect() }
    setPrzeciaga(true)
  }
  const przesun = (e: ReactPointerEvent<HTMLElement>) => {
    const s = start.current
    if (!s) return
    // Nagłówek zawsze zostaje w zasięgu myszy: okna nie da się wypchnąć poza ekran.
    const margines = 64
    const dx = Math.min(Math.max(e.clientX - s.x, margines - s.prostokat.right), window.innerWidth - margines - s.prostokat.left)
    const dy = Math.min(Math.max(e.clientY - s.y, -s.prostokat.top), window.innerHeight - 56 - s.prostokat.top)
    setPrzesuniecie({ x: s.baza.x + dx, y: s.baza.y + dy })
  }
  const zakoncz = () => {
    start.current = null
    setPrzeciaga(false)
  }

  return (
    <div className="fixed inset-0 z-40 grid place-items-center p-4">
      <div className="absolute inset-0 animate-rozjasnij bg-marka-950/40 backdrop-blur-[2px]" onClick={onZamknij} aria-hidden />
      <aside
        ref={okno}
        role="dialog"
        aria-modal="true"
        aria-label={tytul}
        style={{ transform: `translate(${przesuniecie.x}px, ${przesuniecie.y}px)` }}
        className="relative flex max-h-[min(52rem,calc(100dvh-2rem))] w-full max-w-2xl animate-pojaw flex-col overflow-hidden rounded-2xl bg-powierzchnia shadow-2xl ring-1 ring-black/5"
      >
        <header
          onPointerDown={zacznij}
          onPointerMove={przesun}
          onPointerUp={zakoncz}
          onPointerCancel={zakoncz}
          title="Przeciągnij, żeby przesunąć okno"
          className={`flex touch-none select-none items-start justify-between gap-4 border-b border-obramowanie px-6 py-4 ${przeciaga ? 'cursor-grabbing' : 'cursor-grab'}`}
        >
          <div className="flex min-w-0 items-start gap-3">
            <GripHorizontal className="mt-1 size-4 shrink-0 text-neutral-300" aria-hidden />
            <div className="min-w-0">
              <h2 className="truncate text-lg font-semibold tracking-tight text-marka-950">{tytul}</h2>
              {opis && <p className="mt-0.5 text-sm text-tekst-drugorzedny">{opis}</p>}
            </div>
          </div>
          <button type="button" onClick={onZamknij} aria-label="Zamknij" className="rounded-lg p-1.5 text-neutral-500 transition hover:bg-neutral-100 hover:text-marka-900">
            <X className="size-5" />
          </button>
        </header>
        {blad && (
          <div role="alert" className="border-b border-blad/20 bg-blad-tlo px-6 py-2.5 text-sm font-medium text-blad">{blad}</div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {stopka && <footer className="flex flex-wrap items-center gap-2 border-t border-obramowanie bg-neutral-50 px-6 py-3.5">{stopka}</footer>}
      </aside>
    </div>
  )
}

/** Tytuł sekcji wewnątrz długiego formularza. */
export function SekcjaFormularza({ tytul, children }: { tytul: string; children: ReactNode }) {
  return (
    <fieldset className="mb-6 last:mb-0">
      <legend className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">{tytul}</legend>
      <div className="grid gap-4 sm:grid-cols-6">{children}</div>
    </fieldset>
  )
}
