import { FileSpreadsheet, FlaskConical, ShoppingCart } from 'lucide-react'
import { Navigate, NavLink, Route, Routes } from 'react-router'
import { NaglowekStrony } from '../layout/NaglowekStrony'
import { RejestrZakupow } from '../zakupy/RejestrZakupow'
import { Zakupy } from '../zakupy/Zakupy'

const SCIEZKA = '/zakupy'

const ZAKLADKI = [
  { sciezka: 'faktury', nazwa: 'Faktury zakupu', ikona: ShoppingCart, element: <Zakupy /> },
  { sciezka: 'rejestr', nazwa: 'Rejestr zakupów', ikona: FileSpreadsheet, element: <RejestrZakupow /> },
]

// Ścieżki BEZWZGLĘDNE — jak w Kartotekach (względne linki w trasie z gwiazdką dają pętlę przekierowań).
const adres = (zakladka: string) => `${SCIEZKA}/${zakladka}`
const DOMYSLNA = adres('faktury')

export function ZakupyPage() {
  return (
    <>
      <NaglowekStrony tytul="Zakupy" opis="Faktury zakupu towarów i surowców: szkic → zatwierdzenie z własnym numerem → ewentualne anulowanie. Rejestr z VAT naliczonym." />
      <nav className="sticky top-0 z-10 flex items-center overflow-x-auto border-b border-obramowanie bg-powierzchnia px-6 lg:px-8" aria-label="Zakładki zakupów">
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
          title="Do czasu podłączenia KSeF księgowość prowadzi Fakturownia">
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
