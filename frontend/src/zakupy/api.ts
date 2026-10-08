import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { FormaPlatnosci } from '../ustawienia/api'
import type { FiltrStatusu, PozycjaDane, StatusFaktury, StawkaSuma } from '../sprzedaz/api'

export type ZakupDane = {
  seria_id: number | null
  kontrahent_id: number | null // dostawca
  numer_obcy: string // numer faktury dostawcy
  data_wystawienia: string // data na fakturze dostawcy
  data_zakupu: string // data dostawy towaru
  termin_platnosci: string | null
  forma_platnosci: FormaPlatnosci
  uwagi: string
  pozycje: PozycjaDane[]
}

export type ZakupWiersz = {
  id: number
  status: StatusFaktury
  numer: string | null
  numer_obcy: string
  data_wystawienia: string
  data_zakupu: string
  termin_platnosci: string | null
  forma_platnosci: FormaPlatnosci
  dostawca_nazwa: string
  dostawca_nip: string
  suma_netto: number
  suma_vat: number
  suma_brutto: number
}

export type Zakup = ZakupWiersz & {
  seria_id: number | null
  kontrahent_id: number | null
  uwagi: string
  waluta: string
  dostawca_nr_vat_ue: string
  dostawca_adres_ulica: string
  dostawca_kod_pocztowy: string
  dostawca_miejscowosc: string
  dostawca_kraj: string
  nabywca: Record<string, unknown> | null // kopia danych własnej firmy z chwili zatwierdzenia
  pozycje: (PozycjaDane & { lp: number; wartosc_netto: number })[]
  stawki: StawkaSuma[]
  utworzono: string
  zatwierdzono: string | null
  anulowano: string | null
  przyczyna_anulowania: string
  braki: string[]
}

export type ListaZakupow = {
  pozycje: ZakupWiersz[]
  razem: number
  suma_netto: number
  suma_vat: number
  suma_brutto: number
}

export type RejestrZakupow = {
  od: string
  do: string
  wg: 'wystawienia' | 'zakupu'
  stawki: StawkaSuma[]
  netto: number
  vat: number // VAT naliczony
  brutto: number
  dokumenty: ZakupWiersz[]
}

const KLUCZ = ['zakupy'] as const

export type FiltryZakupow = { q: string; status: FiltrStatusu; od?: string; do?: string; offset: number; limit: number }

export function useZakupy(f: FiltryZakupow) {
  const p = new URLSearchParams({ status: f.status, limit: String(f.limit), offset: String(f.offset) })
  if (f.q.trim()) p.set('q', f.q.trim())
  if (f.od) p.set('od', f.od)
  if (f.do) p.set('do', f.do)
  return useQuery({
    queryKey: [...KLUCZ, 'faktury', f],
    queryFn: () => api<ListaZakupow>(`/api/zakupy/faktury?${p}`),
    placeholderData: keepPreviousData,
  })
}

export const useZakup = (id: number | null) =>
  useQuery({
    queryKey: [...KLUCZ, 'faktura', id],
    queryFn: () => api<Zakup>(`/api/zakupy/faktury/${id}`),
    enabled: id !== null,
  })

export const useRejestrZakupow = (od: string, do_: string, wg: RejestrZakupow['wg']) =>
  useQuery({
    queryKey: [...KLUCZ, 'rejestr', od, do_, wg],
    queryFn: () => api<RejestrZakupow>(`/api/zakupy/rejestr?od=${od}&do=${do_}&wg=${wg}`),
    placeholderData: keepPreviousData,
  })

function useOdswiez() {
  const klient = useQueryClient()
  return (f?: Zakup | null) => {
    // Świeża faktura od razu w pamięci podręcznej — okno nie mruga „ładowaniem” po zapisie.
    if (f) klient.setQueryData([...KLUCZ, 'faktura', f.id], f)
    return klient.invalidateQueries({ queryKey: KLUCZ })
  }
}

export function useZapiszZakup() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: ({ id, dane }: { id: number | null; dane: ZakupDane }) =>
      id === null
        ? api<Zakup>('/api/zakupy/faktury', { method: 'POST', body: JSON.stringify(dane) })
        : api<Zakup>(`/api/zakupy/faktury/${id}`, { method: 'PUT', body: JSON.stringify(dane) }),
    onSuccess: (f) => odswiez(f),
  })
}

export function useZatwierdzZakup() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: (id: number) => api<Zakup>(`/api/zakupy/faktury/${id}/zatwierdz`, { method: 'POST' }),
    onSettled: (f) => odswiez(f),
  })
}

export function useAnulujZakup() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: ({ id, przyczyna }: { id: number; przyczyna: string }) =>
      api<Zakup>(`/api/zakupy/faktury/${id}/anuluj`, { method: 'POST', body: JSON.stringify({ przyczyna }) }),
    onSuccess: (f) => odswiez(f),
  })
}

export function useUsunSzkicZakupu() {
  const odswiez = useOdswiez()
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/zakupy/faktury/${id}`, { method: 'DELETE' }),
    onSuccess: () => odswiez(),
  })
}
