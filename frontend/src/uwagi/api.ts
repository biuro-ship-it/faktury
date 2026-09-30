import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export type TypUwagi = 'poprawka' | 'pomysl' | 'blad'
export type StatusUwagi = 'nowa' | 'w_realizacji' | 'zrobiona' | 'odrzucona'

export type Uwaga = {
  id: number
  tresc: string
  typ: TypUwagi
  modul: string | null
  status: StatusUwagi
  autor: string
  utworzono: string
  zmieniono: string | null
}

export const TYPY: Record<TypUwagi, string> = { poprawka: 'Poprawka', pomysl: 'Pomysł', blad: 'Błąd' }

export const STATUSY: Record<StatusUwagi, string> = {
  nowa: 'Nowa',
  w_realizacji: 'W realizacji',
  zrobiona: 'Zrobiona',
  odrzucona: 'Odrzucona',
}

const KLUCZ = ['uwagi']

export function useUwagi() {
  return useQuery({ queryKey: KLUCZ, queryFn: () => api<Uwaga[]>('/api/uwagi') })
}

export function useDodajUwage() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: (dane: { tresc: string; typ: TypUwagi; modul: string | null }) =>
      api<Uwaga>('/api/uwagi', { method: 'POST', body: JSON.stringify(dane) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: KLUCZ }),
  })
}

export function useZmienStatus() {
  const klient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: StatusUwagi }) =>
      api<Uwaga>(`/api/uwagi/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
    onSuccess: () => klient.invalidateQueries({ queryKey: KLUCZ }),
  })
}
