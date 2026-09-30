import { Bug, Lightbulb, LoaderCircle, Wrench } from 'lucide-react'
import { useState } from 'react'
import { NaglowekStrony } from '../layout/NaglowekStrony'
import { OBSZARY } from '../layout/moduly'
import { STATUSY, type StatusUwagi, TYPY, type Uwaga, useUwagi, useZmienStatus } from '../uwagi/api'
import { FormularzUwagi } from '../uwagi/FormularzUwagi'

const FILTRY = {
  otwarte: { etykieta: 'Otwarte', pasuje: (u: Uwaga) => u.status === 'nowa' || u.status === 'w_realizacji' },
  zrobione: { etykieta: 'Zrobione', pasuje: (u: Uwaga) => u.status === 'zrobiona' },
  odrzucone: { etykieta: 'Odrzucone', pasuje: (u: Uwaga) => u.status === 'odrzucona' },
  wszystkie: { etykieta: 'Wszystkie', pasuje: () => true },
} as const
type Filtr = keyof typeof FILTRY

const IKONY_TYPU = { poprawka: Wrench, pomysl: Lightbulb, blad: Bug }

const KOLORY_STATUSU: Record<StatusUwagi, string> = {
  nowa: 'bg-info-tlo text-info',
  w_realizacji: 'bg-zloto-50 text-zloto-800',
  zrobiona: 'bg-sukces-tlo text-sukces',
  odrzucona: 'bg-neutral-100 text-neutral-500',
}

const nazwaModulu = (sciezka: string | null) => OBSZARY.find((m) => m.sciezka === sciezka)?.nazwa ?? 'Cała aplikacja'

const formatDaty = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function WierszUwagi({ uwaga }: { uwaga: Uwaga }) {
  const zmien = useZmienStatus()
  const Ikona = IKONY_TYPU[uwaga.typ]
  const zamknieta = uwaga.status === 'zrobiona' || uwaga.status === 'odrzucona'

  return (
    <li className="flex gap-4 px-5 py-4">
      <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-marka-50 text-marka-800" title={TYPY[uwaga.typ]}>
        <Ikona className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className={`whitespace-pre-wrap text-sm ${zamknieta ? 'text-neutral-500 line-through decoration-neutral-300' : ''}`}>
          {uwaga.tresc}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-neutral-500">
          <span>#{uwaga.id}</span>
          <span>{TYPY[uwaga.typ]}</span>
          <span>{nazwaModulu(uwaga.modul)}</span>
          <span>{formatDaty.format(new Date(uwaga.utworzono))}</span>
          <span>{uwaga.autor}</span>
        </div>
      </div>
      <select
        value={uwaga.status}
        disabled={zmien.isPending}
        onChange={(e) => zmien.mutate({ id: uwaga.id, status: e.target.value as StatusUwagi })}
        aria-label="Status uwagi"
        className={`h-fit shrink-0 cursor-pointer rounded-full border-0 py-1 pl-3 pr-7 text-xs font-medium ${KOLORY_STATUSU[uwaga.status]}`}
      >
        {(Object.keys(STATUSY) as StatusUwagi[]).map((s) => (
          <option key={s} value={s}>
            {STATUSY[s]}
          </option>
        ))}
      </select>
    </li>
  )
}

export function UwagiPage() {
  const uwagi = useUwagi()
  const [filtr, setFiltr] = useState<Filtr>('otwarte')
  const widoczne = (uwagi.data ?? []).filter(FILTRY[filtr].pasuje)

  return (
    <>
      <NaglowekStrony
        tytul="Uwagi do aplikacji"
        opis="Co poprawić, co dopisać, co nie działa. Claude czyta tę listę na początku każdej sesji."
      />
      <div className="grid gap-6 p-6 lg:p-8 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="order-2 min-w-0 xl:order-1">
          <div className="mb-3 flex flex-wrap gap-1 rounded-lg bg-neutral-100 p-1 text-sm w-fit">
            {(Object.keys(FILTRY) as Filtr[]).map((f) => {
              const ile = (uwagi.data ?? []).filter(FILTRY[f].pasuje).length
              return (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFiltr(f)}
                  className={`rounded-md px-3 py-1.5 font-medium transition ${
                    filtr === f ? 'bg-white text-marka-950 shadow-sm' : 'text-neutral-600 hover:text-marka-900'
                  }`}
                >
                  {FILTRY[f].etykieta} <span className="liczby text-neutral-400">{ile}</span>
                </button>
              )
            })}
          </div>

          <div className="overflow-hidden rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
            {uwagi.isPending ? (
              <div className="grid place-items-center py-16">
                <LoaderCircle className="size-6 animate-spin text-marka-700" />
              </div>
            ) : uwagi.isError ? (
              <p className="px-5 py-10 text-center text-sm text-blad">{uwagi.error.message}</p>
            ) : widoczne.length === 0 ? (
              <p className="px-5 py-16 text-center text-sm text-neutral-500">
                {filtr === 'otwarte' ? 'Brak otwartych uwag. Wszystko ogarnięte 🎉' : 'Nic tu nie ma.'}
              </p>
            ) : (
              <ul className="divide-y divide-obramowanie">
                {widoczne.map((u) => (
                  <WierszUwagi key={u.id} uwaga={u} />
                ))}
              </ul>
            )}
          </div>
        </section>

        <aside className="order-1 xl:order-2">
          <div className="rounded-xl border border-obramowanie bg-powierzchnia p-5 shadow-sm xl:sticky xl:top-6">
            <h2 className="mb-4 font-semibold text-marka-950">Nowa uwaga</h2>
            <FormularzUwagi modulStartowy={null} />
          </div>
        </aside>
      </div>
    </>
  )
}
