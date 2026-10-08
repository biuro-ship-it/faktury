import { FileSpreadsheet, FileText, FlaskConical } from 'lucide-react'
import { Navigate, NavLink, Route, Routes } from 'react-router'
import { NaglowekStrony } from '../layout/NaglowekStrony'
import { Faktury } from '../sprzedaz/Faktury'
import { Rejestr } from '../sprzedaz/Rejestr'

const SCIEZKA = '/sprzedaz'

const ZAKLADKI = [
  { sciezka: 'faktury', nazwa: 'Faktury', ikona: FileText, element: <Faktury /> },
  { sciezka: 'rejestr', nazwa: 'Rejestr sprzedaży', ikona: FileSpreadsheet, element: <Rejestr /> },
]

// Ścieżki BEZWZGLĘDNE — jak w Kartotekach (względne linki w trasie z gwiazdką dają pętlę przekierowań).
const adres = (zakladka: string) => `${SCIEZKA}/${zakladka}`
const DOMYSLNA = adres('faktury')

export function SprzedazPage() {
  return (
    <>
      <NaglowekStrony tytul="Sprzedaż" opis="Faktury VAT: szkic → zatwierdzenie z numerem → ewentualne anulowanie. Rejestr z sumami po stawkach." />
      <nav className="sticky top-0 z-10 flex items-center overflow-x-auto border-b border-obramowanie bg-powierzchnia px-6 lg:px-8" aria-label="Zakładki sprzedaży">
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
        <span className="ml-auto hidden items-center gap-1.5 whitespace-nowrap rounded-full bg-zloto-50 px-2.5 py-1 text-xs font-medium text-zloto-800 ring-1 ring-zloto-200 md:inline-flex"
          title="Do czasu podłączenia KSeF obowiązujące faktury wystawia Fakturownia">
          <FlaskConical className="size-3.5" /> Tryb testowy — równolegle z Fakturownią
        </span>
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
