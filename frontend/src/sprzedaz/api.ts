import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { FormaPlatnosci } from '../ustawienia/api'

export type StatusFaktury = 'szkic' | 'zatwierdzony' | 'anulowany'
export type FiltrStatusu = StatusFaktury | 'wszystkie'

export const STATUSY: Record<StatusFaktury, string> = {
  szkic: 'Szkic',
  zatwierdzony: 'Zatwierdzona',
  anulowany: 'Anulowana',
}

export type PozycjaDane = {
  towar_id: number | null
  nazwa: string
  jm: string
  ilosc: string // tekst z kropką, np. "1.5" — bez floatów
  cena_netto: number // grosze
  stawka_vat_kod: string
  gtu: string | null
}

export type FakturaDane = {
  seria_id: number | null
  kontrahent_id: number | null
  data_wystawienia: string
  data_sprzedazy: string
  termin_platnosci: string | null
  forma_platnosci: FormaPlatnosci
  konto_bankowe_id: number | null
  miejsce_wystawienia: string
  wystawiajacy: string
  uwagi: string
  pozycje: PozycjaDane[]
}

export type FakturaWiersz = {
  id: number
  status: StatusFaktury
  numer: string | null
  data_wystawienia: string
  data_sprzedazy: string
  termin_platnosci: string | null
  forma_platnosci: FormaPlatnosci
  nabywca_nazwa: string
  nabywca_nip: string
  suma_netto: number
  suma_vat: number
  suma_brutto: number
}

export type StawkaSuma = { kod: string; nazwa: string; netto: number; vat: number; brutto: number }

export type Faktura = FakturaWiersz & {
  seria_id: number | null
  kontrahent_id: number | null
  konto_bankowe_id: number | null
  miejsce_wystawienia: string
  wystawiajacy: string
  uwagi: string
  waluta: string
  nabywca_nr_vat_ue: string
  nabywca_adres_ulica: string
  nabywca_kod_pocztowy: string
  nabywca_miejscowosc: string
  nabywca_kraj: string
  sprzedawca: Record<string, unknown> & { konto?: { numer: string; bank: string } | null } | null
  pozycje: (PozycjaDane & { lp: number; wartosc_netto: number })[]
  stawki: StawkaSuma[]
  utworzono: string
  zatwierdzono: string | null
  anulowano: string | null
  przyczyna_anulowania: string
  braki: string[]
}

export type ListaFaktur = {
  pozycje: FakturaWiersz[]
  razem: number
  suma_netto: number
  suma_vat: number
  suma_brutto: number
}

export type Rejestr = {
  od: string
  do: string
  wg: 'wystawienia' | 'sprzedazy'
  stawki: StawkaSuma[]
  netto: number
  vat: number
  brutto: number
  dokumenty: FakturaWiersz[]
}

// ---------------------------------------------------------------- Wyliczenia (lustro backendu, na BigInt)

const ILOSC = /^\d{1,10}(?:[.,]\d{1,4})?$/

/** „1,5” → "1.5"; undefined, gdy zapis jest błędny albo ilość nie jest dodatnia. */
export function normalizujIlosc(tekst: string): string | undefined {
  const t = tekst.replace(/\s/g, '')
  if (!ILOSC.test(t)) return undefined
  const kropka = t.replace(',', '.')
  return /^0+(?:\.0+)?$/.test(kropka) ? undefined : kropka
}

const zaokraglij = (licznik: bigint, mianownik: bigint): bigint => {
  // Połówka od zera — tak jak ROUND_HALF_UP w Decimal po stronie serwera.
  const znak = licznik < 0n ? -1n : 1n
  const abs = licznik * znak
  return znak * ((abs * 2n + mianownik) / (mianownik * 2n))
}

/** Ilość × cena (grosze) → wartość w groszach, zaokrąglona do grosza. */
export function wartoscPozycji(ilosc: string, cena: number): number {
  const [calk, ulamek = ''] = ilosc.split('.')
  const wTysiecznych = BigInt(calk + ulamek.padEnd(4, '0'))
  return Number(zaokraglij(wTysiecznych * BigInt(cena), 10000n))
}

export function vatOdNetto(netto: number, procent: number | null): number {
  if (procent === null) return 0
  return Number(zaokraglij(BigInt(netto) * BigInt(procent), 100n))
}

/** "10.0000" → „10”, "1.5000" → „1,5” — bez zbędnych zer z NUMERIC(14,4). */
export function naIlosc(ilosc: string | number): string {
  const t = String(ilosc)
  return (t.includes('.') ? t.replace(/\.?0+$/, '') : t).replace('.', ',')
}

/** IBAN w grupach po 4 znaki — czytelny na ekranie i wydruku. */
export const naIban = (numer: string) => numer.replace(/(.{4})(?=.)/g, '$1 ')

// ---------------------------------------------------------------- Daty

export const dzisISO = () => new Date().toLocaleDateString('sv-SE') // RRRR-MM-DD w czasie lokalnym

export function dodajDni(iso: string, dni: number): string {
  const [r, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(r, m - 1, d + dni)).toISOString().slice(0, 10)
}

export const naDate = (iso: string | null) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('pl-PL') : '—')

/** "2026-10" → pierwszy i ostatni dzień miesiąca. */
export function granicaMiesiaca(miesiac: string): { od: string; do: string } {
  const [r, m] = miesiac.split('-').map(Number)
  return { od: `${miesiac}-01`, do: new Date(Date.UTC(r, m, 0)).toISOString().slice(0, 10) }
}

// ---------------------------------------------------------------- Zapytania

const KLUCZ = ['sprzedaz'] as const

export type FiltryFaktur = { q: string; status: FiltrStatusu; od?: string; do?: string; offset: number; limit: number }

export function useFaktury(f: FiltryFaktur) {
  const p = new URLSearchParams({ status: f.status, limit: String(f.limit), offset: String(f.offset) })
  if (f.q.trim()) p.set('q', f.q.trim())
  if (f.od) p.set('od', f.od)
  if (f.do) p.set('do', f.do)
  return useQuery({
    queryKey: [...KLUCZ, 'faktury', f],
    queryFn: () => api<ListaFaktur>(`/api/sprzedaz/faktury?${p}`),
    placeholderData: keepPreviousData,
  })
}

export const useFaktura = (id: number | null) =>
  useQuery({
    queryKey: [...KLUCZ, 'faktura', id],
    queryFn: () => api<Faktura>(`/api/sprzedaz/faktury/${id}`),
    enabled: id !== null,
  })

export const useRejestr = (od: string, do_: string, wg: Rejestr['wg']) =>
  useQuery({
    queryKey: [...KLUCZ, 'rejestr', od, do_, wg],
    queryFn: () => api<Rejestr>(`/api/sprzedaz/rejestr?od=${od}&do=${do_}&wg=${wg}`),
    placeholderData: keepPreviousData,
  })

function useOdswiez() {
  const klient = useQueryClient()
  return (f?: Faktura | null) => {
    // Świeża faktura od razu w pamięci podręcznej — okno nie mruga „ładowaniem” po zapisie.
    if (f) klient.setQueryData([...KLUCZ, 'faktura', f.id], f)
    return klient.invalidateQueries({ queryKey: KLUCZ })
  }
}

export function useZapiszFakture() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: ({ id, dane }: { id: number | null; dane: FakturaDane }) =>
      id === null
        ? api<Faktura>('/api/sprzedaz/faktury', { method: 'POST', body: JSON.stringify(dane) })
        : api<Faktura>(`/api/sprzedaz/faktury/${id}`, { method: 'PUT', body: JSON.stringify(dane) }),
    onSuccess: (f) => odswiez(f),
  })
}

export function useZatwierdzFakture() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: (id: number) => api<Faktura>(`/api/sprzedaz/faktury/${id}/zatwierdz`, { method: 'POST' }),
    onSettled: (f) => odswiez(f),
  })
}

export function useAnulujFakture() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: ({ id, przyczyna }: { id: number; przyczyna: string }) =>
      api<Faktura>(`/api/sprzedaz/faktury/${id}/anuluj`, { method: 'POST', body: JSON.stringify({ przyczyna }) }),
    onSuccess: (f) => odswiez(f),
  })
}

export function useUsunSzkic() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/sprzedaz/faktury/${id}`, { method: 'DELETE' }),
    onSuccess: () => odswiez(),
  })
}
