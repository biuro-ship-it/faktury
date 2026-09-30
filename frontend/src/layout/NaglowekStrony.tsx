import type { ReactNode } from 'react'

export function NaglowekStrony({ tytul, opis, akcje }: { tytul: string; opis?: string; akcje?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-obramowanie bg-powierzchnia px-6 py-5 lg:px-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-marka-950">{tytul}</h1>
        {opis && <p className="mt-1 max-w-2xl text-sm text-tekst-drugorzedny">{opis}</p>}
      </div>
      {akcje}
    </header>
  )
}
