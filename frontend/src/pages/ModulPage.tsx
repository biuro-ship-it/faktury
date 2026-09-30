import { Construction } from 'lucide-react'
import { NaglowekStrony } from '../layout/NaglowekStrony'
import type { Modul } from '../layout/moduly'

/** Zaślepka modułu — do czasu jego fazy pokazuje, co tu powstanie. */
export function ModulPage({ modul }: { modul: Modul }) {
  const Ikona = modul.ikona
  return (
    <>
      <NaglowekStrony tytul={modul.nazwa} opis={modul.opis} />
      <div className="p-6 lg:p-8">
        <section className="max-w-2xl rounded-xl border border-obramowanie bg-powierzchnia p-6 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="grid size-11 shrink-0 place-items-center rounded-lg bg-marka-100 text-marka-800">
              <Ikona className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-semibold text-marka-950">Moduł w przygotowaniu</h2>
                <span className="inline-flex items-center gap-1 rounded-full bg-zloto-50 px-2 py-0.5 text-xs font-medium text-zloto-800 ring-1 ring-zloto-200">
                  <Construction className="size-3" />
                  Faza {modul.faza}
                </span>
              </div>
              <p className="mt-1 text-sm text-tekst-drugorzedny">Zakres planowany dla tego modułu:</p>
              <ul className="mt-3 space-y-1.5 text-sm">
                {modul.zakres.map((pozycja) => (
                  <li key={pozycja} className="flex gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-marka-400" />
                    {pozycja}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </div>
    </>
  )
}
