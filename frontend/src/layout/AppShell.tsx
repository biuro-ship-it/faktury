import { LogOut, Menu, MessageSquarePlus, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { useAuth, useProfil } from '../auth/AuthProvider'
import { FormularzUwagi } from '../uwagi/FormularzUwagi'
import { MODULY, PULPIT, UWAGI } from './moduly'

/** Pływający przycisk na każdej stronie: uwaga zapisuje się z podpowiedzianym bieżącym modułem. */
function SzybkaUwaga() {
  const { pathname } = useLocation()
  const [otwarte, setOtwarte] = useState(false)
  const [zapisano, setZapisano] = useState(false)
  const biezacyModul = MODULY.find((m) => pathname.startsWith(m.sciezka))?.sciezka ?? null

  useEffect(() => {
    if (!zapisano) return
    const t = setTimeout(() => setZapisano(false), 2500)
    return () => clearTimeout(t)
  }, [zapisano])

  if (pathname.startsWith(UWAGI.sciezka)) return null

  return (
    <>
      {zapisano && (
        <div role="status" className="fixed bottom-20 right-6 z-50 rounded-lg bg-marka-950 px-4 py-2 text-sm text-white shadow-lg">
          Uwaga zapisana ✓
        </div>
      )}
      <button
        type="button"
        onClick={() => setOtwarte(true)}
        className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-zloto-600 px-4 py-3 text-sm font-semibold text-marka-950 shadow-lg ring-1 ring-zloto-700/20 transition hover:bg-zloto-500 hover:shadow-xl"
      >
        <MessageSquarePlus className="size-5" />
        <span className="hidden sm:inline">Zgłoś uwagę</span>
      </button>
      {otwarte && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-marka-950/40 p-4"
          onMouseDown={(e) => e.target === e.currentTarget && setOtwarte(false)}
          onKeyDown={(e) => e.key === 'Escape' && setOtwarte(false)}
        >
          <div role="dialog" aria-modal="true" aria-labelledby="szybka-uwaga" className="w-full max-w-lg rounded-xl bg-powierzchnia p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 id="szybka-uwaga" className="font-semibold text-marka-950">Zgłoś uwagę</h2>
              <button type="button" onClick={() => setOtwarte(false)} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-100" aria-label="Zamknij">
                <X className="size-5" />
              </button>
            </div>
            <FormularzUwagi
              modulStartowy={biezacyModul}
              onDodano={() => {
                setOtwarte(false)
                setZapisano(true)
              }}
            />
          </div>
        </div>
      )}
    </>
  )
}

function LinkMenu({ sciezka, nazwa, ikona: Ikona }: { sciezka: string; nazwa: string; ikona: typeof PULPIT.ikona }) {
  return (
    <NavLink
      to={sciezka}
      end={sciezka === '/'}
      className={({ isActive }) =>
        [
          'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-white/10 text-white'
            : 'text-marka-200 hover:bg-white/5 hover:text-white',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          {/* Złoty akcent tylko na aktywnym elemencie — „ok. 10%” palety. */}
          <span
            className={`absolute inset-y-1.5 left-0 w-1 rounded-r-full bg-zloto-500 transition-opacity ${isActive ? 'opacity-100' : 'opacity-0'}`}
          />
          <Ikona className="size-[18px] shrink-0" strokeWidth={isActive ? 2.25 : 1.75} />
          {nazwa}
        </>
      )}
    </NavLink>
  )
}

export function AppShell() {
  const profil = useProfil()
  const { wyloguj } = useAuth()
  const inicjaly = (profil.imie || profil.email).slice(0, 1).toUpperCase()
  // Na wąskich ekranach menu jest wysuwane; zamykamy je po każdej zmianie strony.
  const [menuOtwarte, setMenuOtwarte] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => setMenuOtwarte(false), [pathname])

  return (
    <div className="flex min-h-dvh">
      {menuOtwarte && (
        <div className="fixed inset-0 z-30 bg-marka-950/40 lg:hidden" onClick={() => setMenuOtwarte(false)} />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex h-dvh w-64 shrink-0 flex-col bg-marka-900 text-white transition-transform lg:sticky lg:top-0 lg:translate-x-0 ${menuOtwarte ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center gap-3 px-5 pb-6 pt-6">
          <img src="/favicon.svg" alt="" className="size-9 rounded-lg ring-1 ring-white/15" />
          <div className="leading-tight">
            <div className="text-[15px] font-semibold tracking-tight">Pluszek</div>
            <div className="text-xs text-marka-300">Księgowość</div>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3" aria-label="Moduły">
          <LinkMenu {...PULPIT} />
          <div className="px-3 pb-1.5 pt-5 text-[11px] font-semibold uppercase tracking-wider text-marka-400">
            Moduły
          </div>
          {MODULY.map((m) => (
            <LinkMenu key={m.sciezka} sciezka={m.sciezka} nazwa={m.nazwa} ikona={m.ikona} />
          ))}
          <div className="px-3 pb-1.5 pt-5 text-[11px] font-semibold uppercase tracking-wider text-marka-400">
            Rozwój
          </div>
          <LinkMenu {...UWAGI} />
        </nav>

        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <div className="grid size-8 shrink-0 place-items-center rounded-full bg-zloto-600 text-sm font-semibold text-marka-950">
              {inicjaly}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-sm font-medium">{profil.imie || profil.email}</div>
              <div className="truncate text-xs text-marka-300">
                {profil.rola === 'admin' ? 'Administrator' : 'Użytkownik'}
              </div>
            </div>
            <button
              type="button"
              onClick={wyloguj}
              title="Wyloguj"
              className="rounded-md p-1.5 text-marka-300 transition-colors hover:bg-white/10 hover:text-white"
            >
              <LogOut className="size-4" />
              <span className="sr-only">Wyloguj</span>
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-obramowanie bg-powierzchnia px-4 py-2.5 lg:hidden">
          <button
            type="button"
            onClick={() => setMenuOtwarte((o) => !o)}
            className="rounded-md p-1.5 text-marka-900 hover:bg-marka-50"
            aria-label={menuOtwarte ? 'Zamknij menu' : 'Otwórz menu'}
          >
            {menuOtwarte ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
          <span className="font-semibold tracking-tight text-marka-950">Pluszek Księgowość</span>
        </div>
        <Outlet />
      </main>
      <SzybkaUwaga />
    </div>
  )
}
