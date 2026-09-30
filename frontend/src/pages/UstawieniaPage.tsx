import { Building2, FileText, Landmark, Percent, Plug } from 'lucide-react'
import { Navigate, NavLink, Route, Routes } from 'react-router'
import { NaglowekStrony } from '../layout/NaglowekStrony'
import { ZakladkaFaktury } from '../ustawienia/ZakladkaFaktury'
import { ZakladkaFirma } from '../ustawienia/ZakladkaFirma'
import { ZakladkaIntegracje } from '../ustawienia/ZakladkaIntegracje'
import { ZakladkaKonta } from '../ustawienia/ZakladkaKonta'
import { ZakladkaStawki } from '../ustawienia/ZakladkaStawki'

const ZAKLADKI = [
  { sciezka: 'firma', nazwa: 'Firma', ikona: Building2, element: <ZakladkaFirma /> },
  { sciezka: 'konta', nazwa: 'Konta bankowe', ikona: Landmark, element: <ZakladkaKonta /> },
  { sciezka: 'faktury', nazwa: 'Faktury', ikona: FileText, element: <ZakladkaFaktury /> },
  { sciezka: 'stawki-vat', nazwa: 'Stawki VAT', ikona: Percent, element: <ZakladkaStawki /> },
  { sciezka: 'integracje', nazwa: 'Integracje', ikona: Plug, element: <ZakladkaIntegracje /> },
]

export function UstawieniaPage() {
  return (
    <>
      <NaglowekStrony tytul="Ustawienia" opis="Dane firmy, konta, numeracja, stawki VAT i integracje." />
      <nav className="sticky top-0 z-10 overflow-x-auto border-b border-obramowanie bg-powierzchnia px-6 lg:px-8" aria-label="Zakładki ustawień">
        <div className="flex gap-1">
          {ZAKLADKI.map((z) => (
            <NavLink
              key={z.sciezka}
              to={z.sciezka}
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
          <Route index element={<Navigate to="firma" replace />} />
          {ZAKLADKI.map((z) => <Route key={z.sciezka} path={z.sciezka} element={z.element} />)}
          <Route path="*" element={<Navigate to="firma" replace />} />
        </Routes>
      </div>
    </>
  )
}
