import { Search } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useProfil } from '../auth/AuthProvider'
import { Karta, Komunikat, Pole, Przycisk, Wejscie } from '../ui/formularz'
import { type Firma, pobierzZBialejListy, useFirma, useZapiszFirme } from './api'

export function ZakladkaFirma() {
  const firma = useFirma()
  if (!firma.data) return <p className="text-sm text-neutral-500">{firma.isError ? firma.error.message : 'Ładowanie…'}</p>
  return <FormularzFirmy poczatkowe={firma.data} />
}

function FormularzFirmy({ poczatkowe }: { poczatkowe: Firma }) {
  const admin = useProfil().rola === 'admin'
  const [dane, setDane] = useState(poczatkowe)
  const zapisz = useZapiszFirme()
  const [bialaLista, setBialaLista] = useState<{ stan: 'nic' | 'laduje' | 'ok' | 'blad'; tekst?: string }>({ stan: 'nic' })

  const ustaw = <K extends keyof Firma>(pole: K) => (e: { target: { value: string } }) => {
    zapisz.reset()
    setDane((d) => ({ ...d, [pole]: e.target.value }))
  }

  const pobierz = async () => {
    setBialaLista({ stan: 'laduje' })
    try {
      const p = await pobierzZBialejListy(dane.nip)
      setDane((d) => ({
        ...d,
        nazwa: p.nazwa,
        nip: p.nip,
        regon: p.regon,
        adres_ulica: p.adres_ulica,
        kod_pocztowy: p.kod_pocztowy,
        miejscowosc: p.miejscowosc,
      }))
      const konta = p.konta.length ? ` Zgłoszone rachunki: ${p.konta.length} — dodasz je w zakładce „Konta bankowe”.` : ''
      setBialaLista({ stan: 'ok', tekst: `Status VAT: ${p.status_vat}. Sprawdź dane i kliknij „Zapisz”.${konta}` })
    } catch (e) {
      setBialaLista({ stan: 'blad', tekst: (e as Error).message })
    }
  }

  const wyslij = (e: FormEvent) => {
    e.preventDefault()
    zapisz.mutate(dane, { onSuccess: (zapisane) => setDane(zapisane) })
  }

  const zmienione = JSON.stringify(dane) !== JSON.stringify(poczatkowe) || zapisz.isSuccess

  return (
    <form onSubmit={wyslij} className="space-y-6">
      <Karta tytul="Dane firmy" opis="Sprzedawca na fakturach i w KSeF. Faktury zapamiętują kopię tych danych z dnia wystawienia.">
        <fieldset disabled={!admin} className="grid gap-4 md:grid-cols-6">
          <Pole etykieta="NIP" className="md:col-span-2">
            <div className="flex gap-2">
              <Wejscie value={dane.nip} onChange={ustaw('nip')} placeholder="0000000000" inputMode="numeric" />
              <Przycisk wariant="drugorzedny" onClick={pobierz} laduje={bialaLista.stan === 'laduje'} disabled={!dane.nip} title="Pobierz dane z Białej Listy MF">
                <Search className="size-4" />
              </Przycisk>
            </div>
          </Pole>
          <Pole etykieta="REGON" className="md:col-span-2">
            <Wejscie value={dane.regon} onChange={ustaw('regon')} inputMode="numeric" />
          </Pole>
          <Pole etykieta="Nazwa skrócona" podpowiedz="W nagłówkach i mailach" className="md:col-span-2">
            <Wejscie value={dane.nazwa_skrocona} onChange={ustaw('nazwa_skrocona')} placeholder="Pluszek" />
          </Pole>
          <Pole etykieta="Pełna nazwa" className="md:col-span-6">
            <Wejscie value={dane.nazwa} onChange={ustaw('nazwa')} />
          </Pole>
          <Pole etykieta="Ulica i numer" className="md:col-span-3">
            <Wejscie value={dane.adres_ulica} onChange={ustaw('adres_ulica')} />
          </Pole>
          <Pole etykieta="Kod pocztowy" className="md:col-span-1">
            <Wejscie value={dane.kod_pocztowy} onChange={ustaw('kod_pocztowy')} placeholder="00-000" />
          </Pole>
          <Pole etykieta="Miejscowość" className="md:col-span-2">
            <Wejscie value={dane.miejscowosc} onChange={ustaw('miejscowosc')} />
          </Pole>
          <Pole etykieta="E-mail" className="md:col-span-2">
            <Wejscie type="email" value={dane.email} onChange={ustaw('email')} />
          </Pole>
          <Pole etykieta="Telefon" className="md:col-span-2">
            <Wejscie value={dane.telefon} onChange={ustaw('telefon')} />
          </Pole>
          <Pole etykieta="Strona WWW" className="md:col-span-2">
            <Wejscie value={dane.www} onChange={ustaw('www')} placeholder="pluszek.pl" />
          </Pole>
        </fieldset>
        {bialaLista.stan === 'ok' && <div className="mt-4"><Komunikat rodzaj="info">{bialaLista.tekst}</Komunikat></div>}
        {bialaLista.stan === 'blad' && <div className="mt-4"><Komunikat rodzaj="blad">{bialaLista.tekst}</Komunikat></div>}
      </Karta>

      {admin ? (
        <div className="flex items-center gap-4">
          <Przycisk type="submit" laduje={zapisz.isPending} disabled={!zmienione}>Zapisz</Przycisk>
          {zapisz.isSuccess && <span className="text-sm text-sukces">Zapisano ✓</span>}
          {zapisz.isError && <span className="text-sm text-blad">{zapisz.error.message}</span>}
        </div>
      ) : (
        <Komunikat rodzaj="info">Zmieniać ustawienia może tylko administrator.</Komunikat>
      )}
    </form>
  )
}
