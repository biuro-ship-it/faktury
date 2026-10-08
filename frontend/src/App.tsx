import { LoaderCircle } from 'lucide-react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { useAuth } from './auth/AuthProvider'
import { AppShell } from './layout/AppShell'
import { KARTOTEKI, MODULY, USTAWIENIA, UWAGI } from './layout/moduly'
import { DashboardPage } from './pages/DashboardPage'
import { KartotekiPage } from './pages/KartotekiPage'
import { LoginPage } from './pages/LoginPage'
import { ModulPage } from './pages/ModulPage'
import { UstawieniaPage } from './pages/UstawieniaPage'
import { UwagiPage } from './pages/UwagiPage'

export function App() {
  const { stan } = useAuth()

  if (stan.status === 'ladowanie') {
    return (
      <div className="grid min-h-dvh place-items-center">
        <LoaderCircle className="size-8 animate-spin text-marka-700" aria-label="Ładowanie" />
      </div>
    )
  }
  if (stan.status === 'wylogowany') return <LoginPage blad={stan.blad} />

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path={`${KARTOTEKI.sciezka}/*`} element={<KartotekiPage />} />
          {MODULY.filter((m) => m.sciezka !== KARTOTEKI.sciezka).map((m) => (
            <Route key={m.sciezka} path={`${m.sciezka}/*`} element={<ModulPage modul={m} />} />
          ))}
          <Route path={UWAGI.sciezka} element={<UwagiPage />} />
          <Route path={`${USTAWIENIA.sciezka}/*`} element={<UstawieniaPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
