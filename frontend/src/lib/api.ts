import { auth } from './firebase'

export class BladApi extends Error {
  readonly status: number

  constructor(status: number, komunikat: string) {
    super(komunikat)
    this.status = status
  }
}

/** Każde żądanie niesie świeży token Firebase — backend weryfikuje go i allowlistę za każdym razem. */
export async function api<T>(sciezka: string, opcje: RequestInit = {}): Promise<T> {
  const token = await auth?.currentUser?.getIdToken()
  const naglowki = new Headers(opcje.headers)
  if (token) naglowki.set('Authorization', `Bearer ${token}`)
  if (opcje.body && !naglowki.has('Content-Type')) naglowki.set('Content-Type', 'application/json')

  let odpowiedz: Response
  try {
    odpowiedz = await fetch(sciezka, { ...opcje, headers: naglowki })
  } catch {
    throw new BladApi(0, 'Brak połączenia z serwerem.')
  }
  if (!odpowiedz.ok) {
    const tresc = await odpowiedz.json().catch(() => null)
    const opis = typeof tresc?.detail === 'string' ? tresc.detail : `Błąd serwera (${odpowiedz.status})`
    throw new BladApi(odpowiedz.status, opis)
  }
  return odpowiedz.json() as Promise<T>
}

export type Profil = {
  id: number
  email: string
  imie: string
  rola: 'admin' | 'uzytkownik'
}
