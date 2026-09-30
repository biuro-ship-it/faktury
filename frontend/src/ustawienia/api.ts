import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export type FormaPlatnosci = 'przelew' | 'gotowka' | 'karta' | 'mobilna'

export type Firma = {
  nazwa: string
  nazwa_skrocona: string
  nip: string
  regon: string
  adres_ulica: string
  kod_pocztowy: string
  miejscowosc: string
  kraj: string
  email: string
  telefon: string
  www: string
  miejsce_wystawienia: string
  termin_platnosci_dni: number
  forma_platnosci: FormaPlatnosci
  wystawiajacy: string
  uwagi_na_fakturze: string
}

export type PodmiotBialaLista = {
  nazwa: string
  nip: string
  regon: string
  status_vat: string
  adres_ulica: string
  kod_pocztowy: string
  miejscowosc: string
  konta: string[]
}

export type Konto = {
  id: number
  nazwa: string
  numer: string
  numer_sformatowany: string
  bank: string
  swift: string
  waluta: string
  domyslne: boolean
  aktywne: boolean
}

export type Stawka = { kod: string; nazwa: string; procent: number | null; aktywna: boolean; domyslna: boolean }

export type OkresResetu = 'miesiac' | 'rok' | 'brak'

export type Seria = {
  id: number
  kod: string
  typ_dokumentu: string
  nazwa: string
  wzorzec: string
  okres_resetu: OkresResetu
  aktywna: boolean
  przyklad: string
  uzyta: boolean
}

export const FORMY_PLATNOSCI: Record<FormaPlatnosci, string> = {
  przelew: 'Przelew',
  gotowka: 'Gotówka',
  karta: 'Karta',
  mobilna: 'Płatność mobilna (BLIK)',
}

export const TYPY_DOKUMENTOW: Record<string, string> = {
  faktura_sprzedazy: 'Faktura sprzedaży',
  korekta_sprzedazy: 'Korekta sprzedaży',
  proforma: 'Proforma',
  faktura_zakupu: 'Faktura zakupu',
  faktura_kosztowa: 'Faktura kosztowa',
  kp: 'KP — kasa przyjmie',
  kw: 'KW — kasa wyda',
  bo: 'BO — bilans otwarcia',
  pz: 'PZ — przyjęcie zewnętrzne',
  wz: 'WZ — wydanie zewnętrzne',
  rw: 'RW — rozchód wewnętrzny',
  pw: 'PW — przyjęcie wewnętrzne',
  mm: 'MM — przesunięcie',
  inwentaryzacja: 'Inwentaryzacja',
  zlecenie_produkcyjne: 'Zlecenie produkcyjne',
}

export const OKRESY_RESETU: Record<OkresResetu, string> = {
  miesiac: 'co miesiąc',
  rok: 'co rok',
  brak: 'nigdy',
}

const K = {
  firma: ['ustawienia', 'firma'],
  konta: ['ustawienia', 'konta'],
  stawki: ['ustawienia', 'stawki'],
  serie: ['ustawienia', 'serie'],
}

export const useFirma = () => useQuery({ queryKey: K.firma, queryFn: () => api<Firma>('/api/ustawienia/firma') })

export function useZapiszFirme() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: (dane: Firma) => api<Firma>('/api/ustawienia/firma', { method: 'PUT', body: JSON.stringify(dane) }),
    onSuccess: (dane) => klient.setQueryData(K.firma, dane),
  })
}

export const pobierzZBialejListy = (nip: string) =>
  api<PodmiotBialaLista>(`/api/ustawienia/biala-lista/${encodeURIComponent(nip)}`)

export const useKonta = () => useQuery({ queryKey: K.konta, queryFn: () => api<Konto[]>('/api/ustawienia/konta') })

export function useDodajKonto() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: (dane: { nazwa: string; numer: string; bank?: string; swift?: string; waluta?: string; domyslne?: boolean }) =>
      api<Konto>('/api/ustawienia/konta', { method: 'POST', body: JSON.stringify(dane) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: K.konta }),
  })
}

export function useZmienKonto() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...dane }: { id: number; nazwa?: string; bank?: string; domyslne?: true; aktywne?: boolean }) =>
      api<Konto>(`/api/ustawienia/konta/${id}`, { method: 'PATCH', body: JSON.stringify(dane) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: K.konta }),
  })
}

export const useStawki = () => useQuery({ queryKey: K.stawki, queryFn: () => api<Stawka[]>('/api/ustawienia/stawki-vat') })

export function useZmienStawke() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: ({ kod, ...dane }: { kod: string; aktywna?: boolean; domyslna?: true }) =>
      api<Stawka>(`/api/ustawienia/stawki-vat/${encodeURIComponent(kod)}`, { method: 'PATCH', body: JSON.stringify(dane) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: K.stawki }),
  })
}

export const useSerie = () => useQuery({ queryKey: K.serie, queryFn: () => api<Seria[]>('/api/ustawienia/serie') })

export const podgladWzorca = (wzorzec: string, okres_resetu: OkresResetu) =>
  api<{ przyklad: string }>('/api/ustawienia/serie/podglad', { method: 'POST', body: JSON.stringify({ wzorzec, okres_resetu }) })

export function useDodajSerie() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: (dane: { kod: string; typ_dokumentu: string; nazwa: string; wzorzec: string; okres_resetu: OkresResetu }) =>
      api<Seria>('/api/ustawienia/serie', { method: 'POST', body: JSON.stringify(dane) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: K.serie }),
  })
}

export function useZmienSerie() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...dane }: { id: number; nazwa?: string; aktywna?: boolean }) =>
      api<Seria>(`/api/ustawienia/serie/${id}`, { method: 'PATCH', body: JSON.stringify(dane) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: K.serie }),
  })
}
