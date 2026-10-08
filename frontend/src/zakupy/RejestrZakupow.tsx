import { Download, FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { naZlote } from '../kartoteki/api'
import { Komunikat, Przycisk, Wejscie } from '../ui/formularz'
import { Segmenty, StanPusty, SzkieletWierszy } from '../ui/kartoteka'
import { dzisISO, granicaMiesiaca, naDate } from '../sprzedaz/api'
import { type RejestrZakupow as TRejestr, useRejestrZakupow } from './api'
import { ZakupOkno } from './ZakupOkno'

const WG: { wartosc: TRejestr['wg']; nazwa: string }[] = [
  { wartosc: 'wystawienia', nazwa: 'Data wystawienia' },
  { wartosc: 'zakupu', nazwa: 'Data zakupu' },
]

/** Kwota do CSV: „1234,56” — bez spacji tysięcy, z przecinkiem (Excel w polskich ustawieniach). */
const doCsv = (grosze: number) => naZlote(grosze).replace(/\s/g, '')

function pobierzCsv(r: TRejestr) {
  const naglowek = ['Numer', 'Numer dostawcy', 'Data wystawienia', 'Data zakupu', 'Dostawca', 'NIP', 'Netto', 'VAT naliczony', 'Brutto']
  const wiersze = r.dokumenty.map((d) => [d.numer ?? '', d.numer_obcy, d.data_wystawienia, d.data_zakupu, d.dostawca_nazwa, d.dostawca_nip,
    doCsv(d.suma_netto), doCsv(d.suma_vat), doCsv(d.suma_brutto)])
  const pole = (v: string) => (/[;"\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
  const tresc = [naglowek, ...wiersze].map((w) => w.map(pole).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['﻿', tresc], { type: 'text/csv;charset=utf-8' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: `rejestr-zakupow_${r.od}_${r.do}.csv` })
  a.click()
  URL.revokeObjectURL(url)
}

export function RejestrZakupow() {
  const [miesiac, setMiesiac] = useState(dzisISO().slice(0, 7))
  const [wg, setWg] = useState<TRejestr['wg']>('wystawienia')
  const [otwarta, setOtwarta] = useState<number | null>(null)
  const { od, do: do_ } = granicaMiesiaca(miesiac || dzisISO().slice(0, 7))
  const rejestr = useRejestrZakupow(od, do_, wg)
  const r = rejestr.data

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Wejscie type="month" aria-label="Miesiąc" value={miesiac} onChange={(e) => setMiesiac(e.target.value)} className="!w-auto" />
        <Segmenty etykieta="Okres według" opcje={WG} wartosc={wg} onZmiana={setWg} />
        <Przycisk wariant="drugorzedny" className="ml-auto" disabled={!r || r.dokumenty.length === 0} onClick={() => r && pobierzCsv(r)}>
          <Download className="size-4" /> Pobierz CSV
        </Przycisk>
      </div>

      {rejestr.isError && <Komunikat rodzaj="blad">{rejestr.error.message}</Komunikat>}

      <div className={`grid gap-3 sm:grid-cols-4 ${rejestr.isPlaceholderData ? 'opacity-60' : ''}`}>
        <Kafel etykieta="Faktur zakupu" wartosc={r ? String(r.dokumenty.length) : '…'} />
        <Kafel etykieta="Netto" wartosc={r ? naZlote(r.netto) : '…'} zl />
        <Kafel etykieta="VAT naliczony" wartosc={r ? naZlote(r.vat) : '…'} zl />
        <Kafel etykieta="Brutto" wartosc={r ? naZlote(r.brutto) : '…'} zl wyrozniony />
      </div>

      <section className="overflow-hidden rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
        <h2 className="border-b border-obramowanie px-5 py-3 font-semibold text-marka-950">Sumy według stawek VAT</h2>
        {!r ? <SzkieletWierszy ile={3} /> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-obramowanie bg-neutral-50/70 text-left text-xs uppercase tracking-wider text-neutral-500">
                <th className="px-5 py-2.5 font-medium">Stawka</th>
                <th className="py-2.5 pr-4 text-right font-medium">Netto</th>
                <th className="py-2.5 pr-4 text-right font-medium">VAT</th>
                <th className="px-5 py-2.5 text-right font-medium">Brutto</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-obramowanie">
              {r.stawki.length === 0 && <tr><td colSpan={4} className="px-5 py-4 text-tekst-drugorzedny">Brak zatwierdzonych zakupów w tym okresie.</td></tr>}
              {r.stawki.map((s) => (
                <tr key={s.kod}>
                  <td className="px-5 py-2.5">{s.nazwa}</td>
                  <td className="liczby py-2.5 pr-4 text-right">{naZlote(s.netto)}</td>
                  <td className="liczby py-2.5 pr-4 text-right">{naZlote(s.vat)}</td>
                  <td className="liczby px-5 py-2.5 text-right font-medium">{naZlote(s.brutto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="overflow-hidden rounded-xl border border-obramowanie bg-powierzchnia shadow-sm">
        <h2 className="border-b border-obramowanie px-5 py-3 font-semibold text-marka-950">Faktury zakupu w rejestrze</h2>
        {!r ? <SzkieletWierszy /> : r.dokumenty.length === 0 ? (
          <StanPusty filtrowane={false} ikona={<FileSpreadsheet className="size-6" />} tytul="Pusty rejestr"
            opis="Do rejestru trafiają tylko zatwierdzone faktury zakupu. Szkice i anulowane są pomijane. Cały VAT jest liczony jako naliczony." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-208 text-sm">
              <thead>
                <tr className="border-b border-obramowanie bg-neutral-50/70 text-left text-xs uppercase tracking-wider text-neutral-500">
                  <th className="px-5 py-2.5 font-medium">Numer</th>
                  <th className="py-2.5 pr-4 font-medium">Nr dostawcy</th>
                  <th className="py-2.5 pr-4 font-medium">{wg === 'wystawienia' ? 'Wystawiona' : 'Zakup'}</th>
                  <th className="py-2.5 pr-4 font-medium">Dostawca</th>
                  <th className="py-2.5 pr-4 text-right font-medium">Netto</th>
                  <th className="py-2.5 pr-4 text-right font-medium">VAT</th>
                  <th className="px-5 py-2.5 text-right font-medium">Brutto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-obramowanie">
                {r.dokumenty.map((d) => (
                  <tr key={d.id} onClick={() => setOtwarta(d.id)} className="cursor-pointer transition hover:bg-marka-50/60">
                    <td className="liczby px-5 py-2.5 font-medium text-marka-900">{d.numer}</td>
                    <td className="liczby py-2.5 pr-4">{d.numer_obcy}</td>
                    <td className="liczby py-2.5 pr-4">{naDate(wg === 'wystawienia' ? d.data_wystawienia : d.data_zakupu)}</td>
                    <td className="py-2.5 pr-4">{d.dostawca_nazwa}</td>
                    <td className="liczby py-2.5 pr-4 text-right">{naZlote(d.suma_netto)}</td>
                    <td className="liczby py-2.5 pr-4 text-right">{naZlote(d.suma_vat)}</td>
                    <td className="liczby px-5 py-2.5 text-right font-medium">{naZlote(d.suma_brutto)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {otwarta !== null && <ZakupOkno id={otwarta} onZamknij={() => setOtwarta(null)} />}
    </div>
  )
}

function Kafel({ etykieta, wartosc, zl = false, wyrozniony = false }: { etykieta: string; wartosc: string; zl?: boolean; wyrozniony?: boolean }) {
  return (
    <div className={`rounded-xl border px-5 py-4 shadow-sm ${wyrozniony ? 'border-marka-900 bg-marka-950 text-white' : 'border-obramowanie bg-powierzchnia'}`}>
      <p className={`text-xs font-medium uppercase tracking-wider ${wyrozniony ? 'text-marka-300' : 'text-neutral-500'}`}>{etykieta}</p>
      <p className={`liczby mt-1 text-2xl font-semibold tracking-tight ${wyrozniony ? 'text-zloto-300' : 'text-marka-950'}`}>
        {wartosc}{zl && <span className="ml-1 text-sm font-medium">zł</span>}
      </p>
    </div>
  )
}
