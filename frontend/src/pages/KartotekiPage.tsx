import { Boxes, Building2, UsersRound } from 'lucide-react'
import { Navigate, NavLink, Route, Routes } from 'react-router'
import { Kontrahenci } from '../kartoteki/Kontrahenci'
import { Pracownicy } from '../kartoteki/Pracownicy'
import { Towary } from '../kartoteki/Towary'
import { NaglowekStrony } from '../layout/NaglowekStrony'

const SCIEZKA = '/kartoteki'

const ZAKLADKI = [
  { sciezka: 'kontrahenci', nazwa: 'Kontrahenci', ikona: Building2, element: <Kontrahenci /> },
  { sciezka: 'towary', nazwa: 'Towary i surowce', ikona: Boxes, element: <Towary /> },
  { sciezka: 'pracownicy', nazwa: 'Pracownicy', ikona: UsersRound, element: <Pracownicy /> },
]

// Ścieżki BEZWZGLĘDNE — jak w Ustawieniach: względne linki w trasie z gwiazdką dają pętlę przekierowań.
const adres = (zakladka: string) => `${SCIEZKA}/${zakladka}`
const DOMYSLNA = adres('kontrahenci')

export function KartotekiPage() {
  return (
    <>
      <NaglowekStrony tytul="Kartoteki" opis="Kontrahenci, towary i surowce, pracownicy — dane, na których opierają się dokumenty." />
      <nav className="sticky top-0 z-10 overflow-x-auto border-b border-obramowanie bg-powierzchnia px-6 lg:px-8" aria-label="Zakładki kartotek">
        <div className="flex gap-1">
          {ZAKLADKI.map((z) => (
            <NavLink
              key={z.sciezka}
              to={adres(z.sciezka)}
              className={({ isActive }) =>
                `flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition ${
                  isActive ? 'border-zloto-600 text-marka-950' : 'border-transparent text-neutral-500 hover:text-marka-900'
                }`
              }
            >
              <z.ikona className="size-4" />
              {z.nazwa}
            </NavLink>
          ))}
        </div>
      </nav>
      <div className="max-w-6xl p-6 lg:p-8">
        <Routes>
          <Route index element={<Navigate to={DOMYSLNA} replace />} />
          {ZAKLADKI.map((z) => <Route key={z.sciezka} path={z.sciezka} element={z.element} />)}
          <Route path="*" element={<Navigate to={DOMYSLNA} replace />} />
        </Routes>
      </div>
    </>
  )
}
