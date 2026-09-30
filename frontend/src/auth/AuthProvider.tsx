import { onAuthStateChanged, signInWithPopup, signOut } from 'firebase/auth'
import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, BladApi, type Profil } from '../lib/api'
import { auth, dostawcaGoogle } from '../lib/firebase'

type StanLogowania =
  | { status: 'ladowanie' }
  | { status: 'wylogowany'; blad: string | null }
  | { status: 'zalogowany'; profil: Profil }

type KontekstLogowania = {
  stan: StanLogowania
  zaloguj: () => Promise<void>
  wyloguj: () => Promise<void>
}

const Kontekst = createContext<KontekstLogowania | null>(null)

/**
 * Wzorzec useAuth z CRM_PLUSZEK, ale allowlista NIE siedzi w kodzie frontu:
 * o dostępie decyduje backend (tabela `uzytkownik`). Front tylko pyta.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [stan, setStan] = useState<StanLogowania>(
    auth ? { status: 'ladowanie' } : { status: 'wylogowany', blad: null },
  )
  // Świeże logowanie (klik „Zaloguj”) zapisujemy w dzienniku; odświeżenie strony tylko sprawdza profil.
  const swiezeLogowanie = useRef(false)

  useEffect(() => {
    if (!auth) return
    const firebaseAuth = auth
    return onAuthStateChanged(firebaseAuth, async (uzytkownikFirebase) => {
      if (!uzytkownikFirebase) {
        setStan((s) => (s.status === 'wylogowany' ? s : { status: 'wylogowany', blad: null }))
        return
      }
      const zapis = swiezeLogowanie.current
      swiezeLogowanie.current = false
      try {
        const profil = zapis
          ? await api<Profil>('/api/auth/logowanie', { method: 'POST' })
          : await api<Profil>('/api/me')
        setStan({ status: 'zalogowany', profil })
      } catch (e) {
        const blad = e instanceof BladApi ? e.message : 'Nie udało się zalogować.'
        await signOut(firebaseAuth)
        setStan({ status: 'wylogowany', blad })
      }
    })
  }, [])

  const zaloguj = useCallback(async () => {
    if (!auth) return
    swiezeLogowanie.current = true
    try {
      await signInWithPopup(auth, dostawcaGoogle)
    } catch (e) {
      swiezeLogowanie.current = false
      const kod = (e as { code?: string }).code
      if (kod === 'auth/popup-closed-by-user' || kod === 'auth/cancelled-popup-request') return
      setStan({ status: 'wylogowany', blad: 'Logowanie Google nie powiodło się. Spróbuj ponownie.' })
    }
  }, [])

  const wyloguj = useCallback(async () => {
    if (auth) await signOut(auth)
  }, [])

  return <Kontekst.Provider value={{ stan, zaloguj, wyloguj }}>{children}</Kontekst.Provider>
}

export function useAuth(): KontekstLogowania {
  const k = useContext(Kontekst)
  if (!k) throw new Error('useAuth musi być użyte wewnątrz <AuthProvider>')
  return k
}

export function useProfil(): Profil {
  const { stan } = useAuth()
  if (stan.status !== 'zalogowany') throw new Error('useProfil wymaga zalogowanego użytkownika')
  return stan.profil
}
