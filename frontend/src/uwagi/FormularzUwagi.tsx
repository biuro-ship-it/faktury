import { LoaderCircle } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { MODULY } from '../layout/moduly'
import { TYPY, type TypUwagi, useDodajUwage } from './api'

export function FormularzUwagi({ modulStartowy, onDodano }: { modulStartowy: string | null; onDodano?: () => void }) {
  const [tresc, setTresc] = useState('')
  const [typ, setTyp] = useState<TypUwagi>('poprawka')
  const [modul, setModul] = useState<string>(modulStartowy ?? '')
  const dodaj = useDodajUwage()

  const wyslij = (e: FormEvent) => {
    e.preventDefault()
    if (!tresc.trim()) return
    dodaj.mutate(
      { tresc, typ, modul: modul || null },
      {
        onSuccess: () => {
          setTresc('')
          onDodano?.()
        },
      },
    )
  }

  return (
    <form onSubmit={wyslij} className="space-y-4">
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Rodzaj uwagi">
        {(Object.keys(TYPY) as TypUwagi[]).map((t) => (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={typ === t}
            onClick={() => setTyp(t)}
            className={`rounded-full px-3 py-1 text-sm font-medium ring-1 transition ${
              typ === t
                ? 'bg-marka-900 text-white ring-marka-900'
                : 'bg-white text-neutral-700 ring-neutral-300 hover:ring-marka-400'
            }`}
          >
            {TYPY[t]}
          </button>
        ))}
      </div>

      <textarea
        value={tresc}
        onChange={(e) => setTresc(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) wyslij(e)
        }}
        rows={4}
        maxLength={5000}
        placeholder="Co poprawić albo dopisać? Np. „Na liście faktur brakuje filtra po kontrahencie”."
        className="block w-full resize-y rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm placeholder:text-neutral-400 focus:border-marka-500 focus:outline-none focus:ring-2 focus:ring-marka-200"
        autoFocus
      />

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-tekst-drugorzedny">
          Dotyczy:
          <select
            value={modul}
            onChange={(e) => setModul(e.target.value)}
            className="rounded-lg border border-neutral-300 bg-white px-2 py-1.5 text-sm text-tekst focus:border-marka-500 focus:outline-none"
          >
            <option value="">całej aplikacji</option>
            {MODULY.map((m) => (
              <option key={m.sciezka} value={m.sciezka}>
                {m.nazwa}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={!tresc.trim() || dodaj.isPending}
          className="ml-auto inline-flex items-center gap-2 rounded-lg bg-marka-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-marka-800 disabled:opacity-50"
        >
          {dodaj.isPending && <LoaderCircle className="size-4 animate-spin" />}
          Zapisz uwagę
        </button>
      </div>
      {dodaj.isError && <p className="text-sm text-blad">{dodaj.error.message}</p>}
      <p className="text-xs text-neutral-500">Ctrl+Enter — szybki zapis</p>
    </form>
  )
}
