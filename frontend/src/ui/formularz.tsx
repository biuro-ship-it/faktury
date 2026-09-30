import { LoaderCircle } from 'lucide-react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'

const KLASA_POLA =
  'block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-tekst placeholder:text-neutral-400 focus:border-marka-500 focus:outline-none focus:ring-2 focus:ring-marka-200 disabled:bg-neutral-50 disabled:text-neutral-500'

export function Pole({ etykieta, podpowiedz, children, className = '' }: { etykieta: string; podpowiedz?: string; children: ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-sm font-medium text-neutral-700">{etykieta}</span>
      {children}
      {podpowiedz && <span className="mt-1 block text-xs text-neutral-500">{podpowiedz}</span>}
    </label>
  )
}

export function Wejscie(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${KLASA_POLA} ${props.className ?? ''}`} />
}

export function Wybor(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${KLASA_POLA} ${props.className ?? ''}`} />
}

export function PoleTekstowe(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${KLASA_POLA} resize-y ${props.className ?? ''}`} />
}

type WariantPrzycisku = 'glowny' | 'drugorzedny' | 'cichy'
const KLASY_PRZYCISKU: Record<WariantPrzycisku, string> = {
  glowny: 'bg-marka-900 text-white shadow-sm hover:bg-marka-800',
  drugorzedny: 'bg-white text-marka-900 ring-1 ring-neutral-300 hover:ring-marka-400 hover:bg-marka-50',
  cichy: 'text-marka-800 hover:bg-marka-50',
}

export function Przycisk({
  wariant = 'glowny',
  laduje = false,
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { wariant?: WariantPrzycisku; laduje?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || laduje}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${KLASY_PRZYCISKU[wariant]} ${className}`}
    >
      {laduje && <LoaderCircle className="size-4 animate-spin" />}
      {children}
    </button>
  )
}

export function Karta({ tytul, opis, akcje, children }: { tytul: string; opis?: string; akcje?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-obramowanie px-5 py-4">
        <div>
          <h2 className="font-semibold text-marka-950">{tytul}</h2>
          {opis && <p className="mt-0.5 text-sm text-tekst-drugorzedny">{opis}</p>}
        </div>
        {akcje}
      </header>
      <div className="p-5">{children}</div>
    </section>
  )
}

export function Komunikat({ rodzaj, children }: { rodzaj: 'sukces' | 'blad' | 'info'; children: ReactNode }) {
  const klasy = {
    sukces: 'bg-sukces-tlo text-sukces border-sukces/20',
    blad: 'bg-blad-tlo text-blad border-blad/20',
    info: 'bg-info-tlo text-info border-info/20',
  }[rodzaj]
  return (
    <div role={rodzaj === 'blad' ? 'alert' : 'status'} className={`rounded-lg border px-4 py-2.5 text-sm ${klasy}`}>
      {children}
    </div>
  )
}

export function Przelacznik({ wlaczony, onZmiana, etykieta, disabled }: { wlaczony: boolean; onZmiana: (v: boolean) => void; etykieta: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={wlaczony}
      aria-label={etykieta}
      disabled={disabled}
      onClick={() => onZmiana(!wlaczony)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition disabled:opacity-50 ${wlaczony ? 'bg-marka-700' : 'bg-neutral-300'}`}
    >
      <span className={`inline-block size-4 rounded-full bg-white shadow transition ${wlaczony ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
    </button>
  )
}
