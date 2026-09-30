import { FileText, Plus } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { useProfil } from '../auth/AuthProvider'
import { Karta, Komunikat, Pole, PoleTekstowe, Przelacznik, Przycisk, Wejscie, Wybor } from '../ui/formularz'
import {
  type Firma,
  FORMY_PLATNOSCI,
  type FormaPlatnosci,
  type OkresResetu,
  OKRESY_RESETU,
  podgladWzorca,
  TYPY_DOKUMENTOW,
  useDodajSerie,
  useFirma,
  useSerie,
  useZapiszFirme,
  useZmienSerie,
} from './api'

export function ZakladkaFaktury() {
  const firma = useFirma()
  return (
    <div className="space-y-6">
      {firma.data ? <DomyslneFaktury poczatkowe={firma.data} /> : <p className="text-sm text-neutral-500">Ładowanie…</p>}
      <SerieNumeracji />
      <Karta tytul="Wygląd faktury (PDF)" opis="Logo, układ i kolory wydruku.">
        <div className="flex items-center gap-3 text-sm text-neutral-500">
          <FileText className="size-5 text-marka-400" />
          Szablon PDF powstanie razem z fakturami (faza 2). Dane z tej zakładki już teraz zasilą każdą fakturę.
        </div>
      </Karta>
    </div>
  )
}

function DomyslneFaktury({ poczatkowe }: { poczatkowe: Firma }) {
  const admin = useProfil().rola === 'admin'
  const [dane, setDane] = useState(poczatkowe)
  const zapisz = useZapiszFirme()
  const ustaw = (pole: keyof Firma) => (e: { target: { value: string } }) => {
    zapisz.reset()
    setDane((d) => ({ ...d, [pole]: pole === 'termin_platnosci_dni' ? Number(e.target.value) : e.target.value }))
  }
  const wyslij = (e: FormEvent) => {
    e.preventDefault()
    // PUT zapisuje cały rekord firmy — bierzemy świeże dane firmy i podmieniamy tylko pola tej zakładki.
    zapisz.mutate({
      ...poczatkowe,
      miejsce_wystawienia: dane.miejsce_wystawienia,
      termin_platnosci_dni: dane.termin_platnosci_dni,
      forma_platnosci: dane.forma_platnosci,
      wystawiajacy: dane.wystawiajacy,
      uwagi_na_fakturze: dane.uwagi_na_fakturze,
    })
  }

  return (
    <form onSubmit={wyslij}>
      <Karta tytul="Domyślne ustawienia faktur" opis="Podpowiadane przy każdej nowej fakturze — na konkretnej fakturze można je zmienić.">
        <fieldset disabled={!admin} className="grid gap-4 md:grid-cols-6">
          <Pole etykieta="Miejsce wystawienia" className="md:col-span-2">
            <Wejscie value={dane.miejsce_wystawienia} onChange={ustaw('miejsce_wystawienia')} />
          </Pole>
          <Pole etykieta="Termin płatności (dni)" className="md:col-span-1">
            <Wejscie type="number" min={0} max={365} value={dane.termin_platnosci_dni} onChange={ustaw('termin_platnosci_dni')} />
          </Pole>
          <Pole etykieta="Forma płatności" className="md:col-span-1">
            <Wybor value={dane.forma_platnosci} onChange={ustaw('forma_platnosci')}>
              {(Object.keys(FORMY_PLATNOSCI) as FormaPlatnosci[]).map((f) => (
                <option key={f} value={f}>{FORMY_PLATNOSCI[f]}</option>
              ))}
            </Wybor>
          </Pole>
          <Pole etykieta="Wystawiający" podpowiedz="Imię i nazwisko na fakturze" className="md:col-span-2">
            <Wejscie value={dane.wystawiajacy} onChange={ustaw('wystawiajacy')} />
          </Pole>
          <Pole etykieta="Uwagi / stopka na fakturze" className="md:col-span-6">
            <PoleTekstowe rows={3} value={dane.uwagi_na_fakturze} onChange={ustaw('uwagi_na_fakturze')} placeholder="np. Dziękujemy za zakupy!" />
          </Pole>
        </fieldset>
        {admin && (
          <div className="mt-5 flex items-center gap-4">
            <Przycisk type="submit" laduje={zapisz.isPending}>Zapisz</Przycisk>
            {zapisz.isSuccess && <span className="text-sm text-sukces">Zapisano ✓</span>}
            {zapisz.isError && <span className="text-sm text-blad">{zapisz.error.message}</span>}
          </div>
        )}
      </Karta>
    </form>
  )
}

function SerieNumeracji() {
  const admin = useProfil().rola === 'admin'
  const serie = useSerie()
  const zmien = useZmienSerie()
  const [formularz, setFormularz] = useState(false)

  return (
    <Karta
      tytul="Serie numeracji"
      opis="Numer nadaje się przy zatwierdzeniu dokumentu — bez dziur i duplikatów. Wzorca używanej serii nie da się zmienić; nowy wzorzec = nowa seria."
      akcje={admin && !formularz && (
        <Przycisk wariant="drugorzedny" onClick={() => setFormularz(true)}>
          <Plus className="size-4" /> Nowa seria
        </Przycisk>
      )}
    >
      {formularz && <NowaSeria onKoniec={() => setFormularz(false)} />}
      {serie.data?.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-obramowanie text-left text-xs uppercase tracking-wider text-neutral-500">
                <th className="py-2 pr-4 font-medium">Kod</th>
                <th className="py-2 pr-4 font-medium">Dokument</th>
                <th className="py-2 pr-4 font-medium">Nazwa</th>
                <th className="py-2 pr-4 font-medium">Wzorzec</th>
                <th className="py-2 pr-4 font-medium">Reset</th>
                <th className="py-2 pr-4 font-medium">Przykład</th>
                <th className="py-2 font-medium">Aktywna</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-obramowanie">
              {serie.data.map((s) => (
                <tr key={s.id} className={s.aktywna ? '' : 'opacity-50'}>
                  <td className="py-2.5 pr-4 font-semibold text-marka-950">{s.kod}</td>
                  <td className="py-2.5 pr-4">{TYPY_DOKUMENTOW[s.typ_dokumentu] ?? s.typ_dokumentu}</td>
                  <td className="py-2.5 pr-4">{s.nazwa}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs">{s.wzorzec}</td>
                  <td className="py-2.5 pr-4">{OKRESY_RESETU[s.okres_resetu]}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs">{s.przyklad}</td>
                  <td className="py-2.5">
                    <Przelacznik etykieta="Aktywna" wlaczony={s.aktywna} disabled={!admin || zmien.isPending}
                      onZmiana={(v) => zmien.mutate({ id: s.id, aktywna: v })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !formularz && (
          <p className="py-6 text-center text-sm text-neutral-500">
            Brak serii. Dodaj np. serię faktur zgodną z numeracją, której używasz dziś, żeby numery szły dalej bez przerwy.
          </p>
        )
      )}
    </Karta>
  )
}

function NowaSeria({ onKoniec }: { onKoniec: () => void }) {
  const [dane, setDane] = useState({
    kod: 'FV',
    typ_dokumentu: 'faktura_sprzedazy',
    nazwa: 'Faktury sprzedaży',
    wzorzec: 'FV/{nr}/{MM}/{RRRR}',
    okres_resetu: 'miesiac' as OkresResetu,
  })
  const [podglad, setPodglad] = useState<{ przyklad?: string; blad?: string }>({})
  const dodaj = useDodajSerie()
  const ustaw = (pole: keyof typeof dane) => (e: { target: { value: string } }) => setDane((d) => ({ ...d, [pole]: e.target.value }))

  // Podgląd numeru na żywo — ta sama walidacja co przy zapisie (backend).
  useEffect(() => {
    const t = setTimeout(() => {
      podgladWzorca(dane.wzorzec, dane.okres_resetu)
        .then((p) => setPodglad({ przyklad: p.przyklad }))
        .catch((e: Error) => setPodglad({ blad: e.message }))
    }, 300)
    return () => clearTimeout(t)
  }, [dane.wzorzec, dane.okres_resetu])

  const wyslij = (e: FormEvent) => {
    e.preventDefault()
    dodaj.mutate(dane, { onSuccess: onKoniec })
  }

  return (
    <form onSubmit={wyslij} className="mb-5 grid gap-4 rounded-lg bg-marka-50/60 p-4 md:grid-cols-6">
      <Pole etykieta="Kod" className="md:col-span-1">
        <Wejscie value={dane.kod} onChange={ustaw('kod')} required className="uppercase" />
      </Pole>
      <Pole etykieta="Dokument" className="md:col-span-2">
        <Wybor value={dane.typ_dokumentu} onChange={ustaw('typ_dokumentu')}>
          {Object.entries(TYPY_DOKUMENTOW).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Wybor>
      </Pole>
      <Pole etykieta="Nazwa" className="md:col-span-3">
        <Wejscie value={dane.nazwa} onChange={ustaw('nazwa')} required />
      </Pole>
      <Pole etykieta="Wzorzec" podpowiedz="{nr}, {nr:04d} (z zerami), {MM}, {RRRR}, {RR}" className="md:col-span-3">
        <Wejscie value={dane.wzorzec} onChange={ustaw('wzorzec')} required className="font-mono" />
      </Pole>
      <Pole etykieta="Numeracja od 1" className="md:col-span-1">
        <Wybor value={dane.okres_resetu} onChange={ustaw('okres_resetu')}>
          {(Object.keys(OKRESY_RESETU) as OkresResetu[]).map((o) => <option key={o} value={o}>{OKRESY_RESETU[o]}</option>)}
        </Wybor>
      </Pole>
      <div className="md:col-span-2">
        <span className="mb-1 block text-sm font-medium text-neutral-700">Pierwszy numer</span>
        <div className={`rounded-lg px-3 py-2 font-mono text-sm ${podglad.blad ? 'bg-blad-tlo text-blad' : 'bg-white text-marka-950 ring-1 ring-neutral-200'}`}>
          {podglad.blad ?? podglad.przyklad ?? '…'}
        </div>
      </div>
      <div className="flex gap-2 md:col-span-6">
        <Przycisk type="submit" laduje={dodaj.isPending} disabled={!!podglad.blad}>Dodaj serię</Przycisk>
        <Przycisk wariant="cichy" onClick={onKoniec}>Anuluj</Przycisk>
      </div>
      {dodaj.isError && <div className="md:col-span-6"><Komunikat rodzaj="blad">{dodaj.error.message}</Komunikat></div>}
    </form>
  )
}
