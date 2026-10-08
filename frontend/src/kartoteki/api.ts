import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export type Aktywnosc = 'tak' | 'nie' | 'wszystkie'
export type Lista<T> = { pozycje: T[]; razem: number }
type Zapytanie = { q: string; aktywnosc: Aktywnosc; offset: number; limit: number }

// ---------------------------------------------------------------- Kontrahenci

export type TypKontrahenta = 'firma' | 'osoba_fizyczna'

export type KontrahentDane = {
  typ: TypKontrahenta
  nazwa: string
  nip: string
  nr_vat_ue: string
  regon: string
  adres_ulica: string
  kod_pocztowy: string
  miejscowosc: string
  kraj: string
  email: string
  telefon: string
  jest_odbiorca: boolean
  jest_dostawca: boolean
  termin_platnosci_dni: number | null
  uwagi: string
  aktywny: boolean
}
export type Kontrahent = KontrahentDane & { id: number }
export type RolaKontrahenta = 'wszyscy' | 'odbiorcy' | 'dostawcy'

export const PUSTY_KONTRAHENT: KontrahentDane = {
  typ: 'firma', nazwa: '', nip: '', nr_vat_ue: '', regon: '', adres_ulica: '', kod_pocztowy: '', miejscowosc: '',
  kraj: 'PL', email: '', telefon: '', jest_odbiorca: true, jest_dostawca: false, termin_platnosci_dni: null,
  uwagi: '', aktywny: true,
}

// ---------------------------------------------------------------- Towary

export type TypTowaru = 'towar_handlowy' | 'surowiec' | 'wyrob_gotowy' | 'usluga'

export const TYPY_TOWARU: Record<TypTowaru, string> = {
  towar_handlowy: 'Towar handlowy',
  surowiec: 'Surowiec',
  wyrob_gotowy: 'Wyrób gotowy',
  usluga: 'Usługa',
}

export type TowarDane = {
  symbol: string
  nazwa: string
  typ: TypTowaru
  jm: string
  stawka_vat_kod: string
  gtu: string | null
  cena_sprzedazy_netto: number | null // grosze
  ean: string
  uwagi: string
  aktywny: boolean
}
export type Towar = TowarDane & { id: number; stawka_vat_nazwa: string; magazynowy: boolean }

export const PUSTY_TOWAR: TowarDane = {
  symbol: '', nazwa: '', typ: 'towar_handlowy', jm: 'szt.', stawka_vat_kod: '', gtu: null, cena_sprzedazy_netto: null,
  ean: '', uwagi: '', aktywny: true,
}

export const JEDNOSTKI = ['szt.', 'kg', 'g', 'l', 'ml', 'm', 'mb', 'm2', 'm3', 'kpl.', 'op.', 'godz.', 'usł.']
export const KODY_GTU = Array.from({ length: 13 }, (_, i) => `GTU_${String(i + 1).padStart(2, '0')}`)

// ---------------------------------------------------------------- Pracownicy

export type PracownikDane = {
  imie: string
  nazwisko: string
  stanowisko: string
  email: string
  telefon: string
  data_zatrudnienia: string | null
  data_zwolnienia: string | null
  uwagi: string
  aktywny: boolean
}
export type Pracownik = PracownikDane & { id: number }

export const PUSTY_PRACOWNIK: PracownikDane = {
  imie: '', nazwisko: '', stanowisko: '', email: '', telefon: '', data_zatrudnienia: null, data_zwolnienia: null,
  uwagi: '', aktywny: true,
}

// ---------------------------------------------------------------- Pieniądze (grosze ↔ tekst, bez floatów)

/** „12,50” / „12.5” / „1 250” → 1250 groszy; null dla pustego pola; undefined dla błędnego zapisu. */
export function naGrosze(tekst: string): number | null | undefined {
  const czysty = tekst.replace(/\s/g, '').replace(',', '.')
  if (czysty === '') return null
  const m = /^(\d{1,10})(?:\.(\d{1,2}))?$/.exec(czysty)
  if (!m) return undefined
  return Number(m[1]) * 100 + Number((m[2] ?? '').padEnd(2, '0'))
}

/** 125000 → „1 250,00” (pełne złote formatowane Intl, grosze doklejone z liczby całkowitej). */
export function naZlote(grosze: number | null): string {
  if (grosze === null) return ''
  const zlote = new Intl.NumberFormat('pl-PL').format(Math.trunc(grosze / 100))
  return `${zlote},${String(grosze % 100).padStart(2, '0')}`
}

// ---------------------------------------------------------------- Zapytania

const parametry = (z: Zapytanie, reszta: Record<string, string | undefined> = {}) => {
  const p = new URLSearchParams({ aktywnosc: z.aktywnosc, limit: String(z.limit), offset: String(z.offset) })
  if (z.q.trim()) p.set('q', z.q.trim())
  for (const [k, v] of Object.entries(reszta)) if (v) p.set(k, v)
  return p.toString()
}

function uzyjListy<T>(klucz: string, sciezka: string, z: Zapytanie, reszta?: Record<string, string | undefined>) {
  return useQuery({
    queryKey: ['kartoteki', klucz, z, reszta],
    queryFn: () => api<Lista<T>>(`/api/kartoteki/${sciezka}?${parametry(z, reszta)}`),
    placeholderData: keepPreviousData, // lista nie mruga przy każdej literze w szukajce
  })
}

function uzyjZapisu<D, W extends { id: number }>(klucz: string, sciezka: string) {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, dane }: { id: number | null; dane: D }) =>
      id === null
        ? api<W>(`/api/kartoteki/${sciezka}`, { method: 'POST', body: JSON.stringify(dane) })
        : api<W>(`/api/kartoteki/${sciezka}/${id}`, { method: 'PUT', body: JSON.stringify(dane) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: ['kartoteki', klucz] }),
  })
}

export const useKontrahenci = (z: Zapytanie, rola: RolaKontrahenta) =>
  uzyjListy<Kontrahent>('kontrahenci', 'kontrahenci', z, { rola: rola === 'wszyscy' ? undefined : rola })
export const useZapiszKontrahenta = () => uzyjZapisu<KontrahentDane, Kontrahent>('kontrahenci', 'kontrahenci')

export const useTowary = (z: Zapytanie, typ: TypTowaru | 'wszystkie') =>
  uzyjListy<Towar>('towary', 'towary', z, { typ: typ === 'wszystkie' ? undefined : typ })
export const useZapiszTowar = () => uzyjZapisu<TowarDane, Towar>('towary', 'towary')

export const usePracownicy = (z: Zapytanie) => uzyjListy<Pracownik>('pracownicy', 'pracownicy', z)
export const useZapiszPracownika = () => uzyjZapisu<PracownikDane, Pracownik>('pracownicy', 'pracownicy')
