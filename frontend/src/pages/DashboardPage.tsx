import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { useProfil } from '../auth/AuthProvider'
import { NaglowekStrony } from '../layout/NaglowekStrony'
import { MODULY, USTAWIENIA } from '../layout/moduly'

const KAFLE = [
  { etykieta: 'Sprzedaż w tym miesiącu', faza: 2 },
  { etykieta: 'Należności przeterminowane', faza: 3 },
  { etykieta: 'Stan kasy', faza: 3 },
  { etykieta: 'Stan rachunku bankowego', faza: 3 },
]

export function DashboardPage() {
  const profil = useProfil()
  const dzis = new Intl.DateTimeFormat('pl-PL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())

  return (
    <>
      <NaglowekStrony
        tytul={`Dzień dobry${profil.imie ? `, ${profil.imie}` : ''}`}
        opis={dzis.charAt(0).toUpperCase() + dzis.slice(1)}
      />
      <div className="space-y-8 p-6 lg:p-8">
        <section aria-label="Wskaźniki">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {KAFLE.map((k) => (
              <div key={k.etykieta} className="rounded-xl border border-obramowanie bg-powierzchnia p-5 shadow-sm">
                <div className="text-sm text-tekst-drugorzedny">{k.etykieta}</div>
                <div className="liczby mt-2 text-2xl font-semibold tracking-tight text-neutral-300">— zł</div>
                <div className="mt-3 text-xs text-neutral-500">Dane od fazy {k.faza}</div>
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="moduly-naglowek">
          <h2 id="moduly-naglowek" className="mb-3 text-sm font-semibold uppercase tracking-wider text-neutral-500">
            Moduły
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {MODULY.map((m) => (
              <Link
                key={m.sciezka}
                to={m.sciezka}
                className="group flex items-center gap-4 rounded-xl border border-obramowanie bg-powierzchnia p-4 shadow-sm transition hover:border-marka-300 hover:shadow-md"
              >
                <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-marka-100 text-marka-800 transition group-hover:bg-marka-900 group-hover:text-white">
                  <m.ikona className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-marka-950">{m.nazwa}</div>
                  <div className="truncate text-xs text-tekst-drugorzedny">Faza {m.faza}</div>
                </div>
                <ChevronRight className="size-4 text-neutral-400 transition group-hover:translate-x-0.5 group-hover:text-marka-700" />
              </Link>
            ))}
            <Link
              to={USTAWIENIA.sciezka}
              className="group flex items-center gap-4 rounded-xl border border-obramowanie bg-powierzchnia p-4 shadow-sm transition hover:border-marka-300 hover:shadow-md"
            >
              <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-marka-100 text-marka-800 transition group-hover:bg-marka-900 group-hover:text-white">
                <USTAWIENIA.ikona className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-marka-950">{USTAWIENIA.nazwa}</div>
                <div className="truncate text-xs text-tekst-drugorzedny">Firma, konta, numeracja, VAT</div>
              </div>
              <ChevronRight className="size-4 text-neutral-400 transition group-hover:translate-x-0.5 group-hover:text-marka-700" />
            </Link>
          </div>
        </section>
      </div>
    </>
  )
}
