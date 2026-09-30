import { Download, Plus, Star } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useProfil } from '../auth/AuthProvider'
import { Karta, Komunikat, Pole, Przelacznik, Przycisk, Wejscie } from '../ui/formularz'
import { type Konto, pobierzZBialejListy, useDodajKonto, useFirma, useKonta, useZmienKonto } from './api'

export function ZakladkaKonta() {
  const admin = useProfil().rola === 'admin'
  const konta = useKonta()
  const [formularz, setFormularz] = useState(false)

  return (
    <div className="space-y-6">
      <Karta
        tytul="Konta bankowe"
        opis="Konto domyślne trafia na faktury. Numeru konta nie zmienia się — błędne konto wyłącz i dodaj nowe."
        akcje={admin && !formularz && (
          <Przycisk wariant="drugorzedny" onClick={() => setFormularz(true)}>
            <Plus className="size-4" /> Dodaj konto
          </Przycisk>
        )}
      >
        {formularz && <NoweKonto onKoniec={() => setFormularz(false)} />}
        {konta.isPending ? (
          <p className="text-sm text-neutral-500">Ładowanie…</p>
        ) : konta.data?.length ? (
          <ul className="divide-y divide-obramowanie">
            {konta.data.map((k) => <WierszKonta key={k.id} konto={k} admin={admin} />)}
          </ul>
        ) : (
          !formularz && <p className="py-6 text-center text-sm text-neutral-500">Nie dodano jeszcze żadnego konta.</p>
        )}
      </Karta>
      {admin && <KontaZBialejListy zapisane={konta.data ?? []} />}
    </div>
  )
}

function WierszKonta({ konto, admin }: { konto: Konto; admin: boolean }) {
  const zmien = useZmienKonto()
  return (
    <li className={`flex flex-wrap items-center gap-4 py-3 ${konto.aktywne ? '' : 'opacity-50'}`}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-marka-950">{konto.nazwa}</span>
          {konto.domyslne && (
            <span className="inline-flex items-center gap-1 rounded-full bg-zloto-50 px-2 py-0.5 text-xs font-medium text-zloto-800 ring-1 ring-zloto-200">
              <Star className="size-3 fill-current" /> domyślne {konto.waluta}
            </span>
          )}
        </div>
        <div className="liczby mt-0.5 font-mono text-sm text-neutral-700">{konto.numer_sformatowany}</div>
        <div className="text-xs text-neutral-500">{[konto.bank, konto.swift, konto.waluta].filter(Boolean).join(' · ')}</div>
      </div>
      {admin && (
        <div className="flex items-center gap-3">
          {!konto.domyslne && konto.aktywne && (
            <Przycisk wariant="cichy" onClick={() => zmien.mutate({ id: konto.id, domyslne: true })}>Ustaw jako domyślne</Przycisk>
          )}
          <Przelacznik etykieta="Aktywne" wlaczony={konto.aktywne} disabled={zmien.isPending}
            onZmiana={(v) => zmien.mutate({ id: konto.id, aktywne: v })} />
        </div>
      )}
      {zmien.isError && <p className="w-full text-sm text-blad">{zmien.error.message}</p>}
    </li>
  )
}

function NoweKonto({ onKoniec, numerStartowy = '' }: { onKoniec: () => void; numerStartowy?: string }) {
  const [dane, setDane] = useState({ nazwa: '', numer: numerStartowy, bank: '', waluta: 'PLN' })
  const dodaj = useDodajKonto()
  const wyslij = (e: FormEvent) => {
    e.preventDefault()
    dodaj.mutate(dane, { onSuccess: onKoniec })
  }
  const ustaw = (pole: keyof typeof dane) => (e: { target: { value: string } }) => setDane((d) => ({ ...d, [pole]: e.target.value }))

  return (
    <form onSubmit={wyslij} className="mb-5 grid gap-4 rounded-lg bg-marka-50/60 p-4 md:grid-cols-6">
      <Pole etykieta="Nazwa" podpowiedz="np. „mBank firmowe”" className="md:col-span-2">
        <Wejscie value={dane.nazwa} onChange={ustaw('nazwa')} required autoFocus />
      </Pole>
      <Pole etykieta="Numer konta" className="md:col-span-4">
        <Wejscie value={dane.numer} onChange={ustaw('numer')} required placeholder="00 0000 0000 0000 0000 0000 0000" className="font-mono" />
      </Pole>
      <Pole etykieta="Bank" className="md:col-span-3">
        <Wejscie value={dane.bank} onChange={ustaw('bank')} />
      </Pole>
      <Pole etykieta="Waluta" className="md:col-span-1">
        <Wejscie value={dane.waluta} onChange={ustaw('waluta')} maxLength={3} className="uppercase" />
      </Pole>
      <div className="flex items-end gap-2 md:col-span-2">
        <Przycisk type="submit" laduje={dodaj.isPending}>Dodaj</Przycisk>
        <Przycisk wariant="cichy" onClick={onKoniec}>Anuluj</Przycisk>
      </div>
      {dodaj.isError && <p className="text-sm text-blad md:col-span-6">{dodaj.error.message}</p>}
    </form>
  )
}

function KontaZBialejListy({ zapisane }: { zapisane: Konto[] }) {
  const firma = useFirma()
  const [stan, setStan] = useState<{ konta?: string[]; blad?: string; laduje?: boolean }>({})
  const [dodawane, setDodawane] = useState<string | null>(null)
  const nip = firma.data?.nip ?? ''
  const zapisaneNumery = new Set(zapisane.map((k) => k.numer_sformatowany))

  const pobierz = async () => {
    setStan({ laduje: true })
    try {
      setStan({ konta: (await pobierzZBialejListy(nip)).konta })
    } catch (e) {
      setStan({ blad: (e as Error).message })
    }
  }

  return (
    <Karta
      tytul="Rachunki zgłoszone w Białej Liście MF"
      opis="Na fakturach warto podawać tylko konta z Białej Listy — kontrahent płacący na inne ryzykuje sankcje."
      akcje={
        <Przycisk wariant="drugorzedny" onClick={pobierz} laduje={stan.laduje} disabled={!nip} title={nip ? '' : 'Najpierw wpisz NIP w zakładce Firma'}>
          <Download className="size-4" /> Sprawdź
        </Przycisk>
      }
    >
      {!nip && <p className="text-sm text-neutral-500">Uzupełnij NIP w zakładce „Firma”, żeby sprawdzić zgłoszone rachunki.</p>}
      {stan.blad && <Komunikat rodzaj="blad">{stan.blad}</Komunikat>}
      {stan.konta && stan.konta.length === 0 && <p className="text-sm text-neutral-500">Brak zgłoszonych rachunków.</p>}
      {stan.konta && stan.konta.length > 0 && (
        <ul className="divide-y divide-obramowanie">
          {stan.konta.map((numer) => (
            <li key={numer} className="py-2">
              <div className="flex items-center justify-between gap-4">
                <span className="liczby font-mono text-sm">{numer}</span>
                {zapisaneNumery.has(numer) ? (
                  <span className="text-xs text-sukces">na liście ✓</span>
                ) : (
                  <Przycisk wariant="cichy" onClick={() => setDodawane(numer)}>Dodaj</Przycisk>
                )}
              </div>
              {dodawane === numer && <div className="mt-3"><NoweKonto numerStartowy={numer} onKoniec={() => setDodawane(null)} /></div>}
            </li>
          ))}
        </ul>
      )}
    </Karta>
  )
}
