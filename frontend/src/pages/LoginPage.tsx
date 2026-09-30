import { LoaderCircle, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../auth/AuthProvider'
import { firebaseSkonfigurowany } from '../lib/firebase'

function LogoGoogle() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.43.34-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.78.43 3.45 1.18 4.93l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15A10.96 10.96 0 0 0 12 1 11 11 0 0 0 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
    </svg>
  )
}

export function LoginPage({ blad }: { blad: string | null }) {
  const { zaloguj } = useAuth()
  const [trwa, setTrwa] = useState(false)

  const kliknij = async () => {
    setTrwa(true)
    await zaloguj()
    setTrwa(false)
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,560px)]">
      <div className="relative hidden overflow-hidden bg-marka-900 lg:block">
        {/* Delikatna faktura: linie jak w księdze rachunkowej. */}
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: 'repeating-linear-gradient(0deg, #fff 0 1px, transparent 1px 40px)' }}
        />
        <div className="absolute inset-y-0 left-24 w-px bg-zloto-500/40" />
        <div className="relative flex h-full flex-col justify-between p-14 text-white">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" className="size-10 rounded-lg ring-1 ring-white/15" />
            <span className="text-lg font-semibold tracking-tight">Pluszek</span>
          </div>
          <div className="max-w-md">
            <p className="text-4xl font-semibold leading-tight tracking-tight">
              Sprzedaż, magazyn i finanse
              <span className="text-zloto-400"> w jednym miejscu.</span>
            </p>
            <p className="mt-4 text-marka-200">
              Każdy zatwierdzony dokument jest nienaruszalny, a ewidencja zawsze się bilansuje.
            </p>
          </div>
          <p className="text-sm text-marka-300">System wewnętrzny — tylko dla osób z firmy.</p>
        </div>
      </div>

      <div className="flex items-center justify-center bg-powierzchnia px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img src="/favicon.svg" alt="" className="size-10 rounded-lg" />
            <span className="text-lg font-semibold tracking-tight text-marka-950">Pluszek Księgowość</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-marka-950">Zaloguj się</h1>
          <p className="mt-2 text-sm text-tekst-drugorzedny">Użyj firmowego konta Google.</p>

          {blad && (
            <div role="alert" className="mt-6 rounded-lg border border-blad/20 bg-blad-tlo px-4 py-3 text-sm text-blad">
              {blad}
            </div>
          )}

          {firebaseSkonfigurowany ? (
            <button
              type="button"
              onClick={kliknij}
              disabled={trwa}
              className="mt-8 flex w-full items-center justify-center gap-3 rounded-lg border border-neutral-300 bg-white px-4 py-2.5 text-sm font-medium text-neutral-800 shadow-sm transition hover:border-marka-400 hover:bg-marka-50 disabled:opacity-60"
            >
              {trwa ? <LoaderCircle className="size-5 animate-spin text-marka-700" /> : <LogoGoogle />}
              Zaloguj przez Google
            </button>
          ) : (
            <div className="mt-8 rounded-lg border border-ostrzezenie/20 bg-ostrzezenie-tlo px-4 py-3 text-sm text-ostrzezenie">
              Brak konfiguracji Firebase. Uzupełnij <code className="font-mono">frontend/.env.local</code> (wzór w <code className="font-mono">.env.example</code>).
            </div>
          )}

          <p className="mt-8 flex items-center gap-2 text-xs text-neutral-500">
            <ShieldCheck className="size-4 text-marka-600" />
            Dostęp mają tylko konta dodane przez administratora.
          </p>
        </div>
      </div>
    </div>
  )
}
