import { LoaderCircle } from 'lucide-react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { useAuth } from './auth/AuthProvider'
import { AppShell } from './layout/AppShell'
import { MODULY } from './layout/moduly'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { ModulPage } from './pages/ModulPage'

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
          {MODULY.map((m) => (
            <Route key={m.sciezka} path={`${m.sciezka}/*`} element={<ModulPage modul={m} />} />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
