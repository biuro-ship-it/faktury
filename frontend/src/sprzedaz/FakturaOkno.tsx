import { AlertTriangle, Ban, CheckCircle2, FileCheck2, LoaderCircle, Plus, Trash2, X } from 'lucide-react'
import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { naGrosze, naZlote, type Kontrahent, type Lista, type Towar } from '../kartoteki/api'
import { api } from '../lib/api'
import { Komunikat, Pole, PoleTekstowe, Przycisk, Wejscie, Wybor } from '../ui/formularz'
import { Panel, Plakietka, SekcjaFormularza } from '../ui/kartoteka'
import { Podpowiedzi } from '../ui/Podpowiedzi'
import { FORMY_PLATNOSCI, type FormaPlatnosci, useFirma, useKonta, useSerie, useStawki } from '../ustawienia/api'
import {
  dodajDni, dzisISO, type Faktura, type FakturaDane, naDate, naIban, naIlosc, normalizujIlosc, STATUSY, useAnulujFakture, useFaktura,
  useUsunSzkic, useZapiszFakture, useZatwierdzFakture, vatOdNetto, wartoscPozycji,
} from './api'

export const TON_STATUSU = { szkic: 'zloty', zatwierdzony: 'zielony', anulowany: 'szary' } as const

/** Okno faktury: szkic otwiera się w edytorze, zatwierdzona i anulowana — w podglądzie (tylko do odczytu). */
export function FakturaOkno({ id: poczatkoweId, onZamknij }: { id: number | null; onZamknij: () => void }) {
  const [id, setId] = useState(poczatkoweId)
  const faktura = useFaktura(id)

  if (id !== null && faktura.isPending) {
    return (
      <Panel tytul="Faktura" onZamknij={onZamknij} szerokie>
        <div className="grid place-items-center py-16"><LoaderCircle className="size-6 animate-spin text-marka-700" /></div>
      </Panel>
    )
  }
  if (faktura.isError) {
    return <Panel tytul="Faktura" onZamknij={onZamknij}><Komunikat rodzaj="blad">{faktura.error.message}</Komunikat></Panel>
  }
  if (faktura.data && faktura.data.status !== 'szkic') return <PodgladFaktury f={faktura.data} onZamknij={onZamknij} />
  // Bez `key`: po pierwszym zapisie nowej faktury edytor zostaje ten sam (nie traci stanu), dostaje tylko id.
  return <EdytorFaktury poczatkowa={faktura.data ?? null} onZapisano={setId} onZamknij={onZamknij} />
}

// ---------------------------------------------------------------- Edytor szkicu

type Wiersz = {
  klucz: number
  towar_id: number | null
  nazwa: string
  jm: string
  ilosc: string
  cena: string // zł jako tekst, np. „12,50”
  stawka_vat_kod: string
  gtu: string | null
}

type NabywcaWidok = { id: number; nazwa: string; nip: string; adres: string; termin: number | null }

let licznikWierszy = 0
const nowyWiersz = (stawka = ''): Wiersz => ({
  klucz: ++licznikWierszy, towar_id: null, nazwa: '', jm: 'szt.', ilosc: '1', cena: '', stawka_vat_kod: stawka, gtu: null,
})

const szukajKontrahentow = (q: string) =>
  api<Lista<Kontrahent>>(`/api/kartoteki/kontrahenci?rola=odbiorcy&limit=8&q=${encodeURIComponent(q)}`).then((l) => l.pozycje)
const szukajTowarow = (q: string) =>
  api<Lista<Towar>>(`/api/kartoteki/towary?limit=8&q=${encodeURIComponent(q)}`).then((l) => l.pozycje.filter((t) => t.typ !== 'surowiec'))

const adresKontrahenta = (k: { adres_ulica: string; kod_pocztowy: string; miejscowosc: string }) =>
  [k.adres_ulica, [k.kod_pocztowy, k.miejscowosc].filter(Boolean).join(' ')].filter(Boolean).join(', ')

function EdytorFaktury({ poczatkowa, onZapisano, onZamknij }: {
  poczatkowa: Faktura | null
  onZapisano: (id: number) => void
  onZamknij: () => void
}) {
  const firma = useFirma()
  const serie = useSerie()
  const konta = useKonta()
  const stawki = useStawki()
  const zapisz = useZapiszFakture()
  const zatwierdz = useZatwierdzFakture()
  const usun = useUsunSzkic()

  const dzis = dzisISO()
  const [nagl, setNagl] = useState({
    seria_id: poczatkowa?.seria_id ?? null,
    data_wystawienia: poczatkowa?.data_wystawienia ?? dzis,
    data_sprzedazy: poczatkowa?.data_sprzedazy ?? dzis,
    termin_platnosci: poczatkowa?.termin_platnosci ?? null,
    forma_platnosci: (poczatkowa?.forma_platnosci ?? 'przelew') as FormaPlatnosci,
    konto_bankowe_id: poczatkowa?.konto_bankowe_id ?? null,
    miejsce_wystawienia: poczatkowa?.miejsce_wystawienia ?? '',
    wystawiajacy: poczatkowa?.wystawiajacy ?? '',
    uwagi: poczatkowa?.uwagi ?? '',
  })
  const [nabywca, setNabywca] = useState<NabywcaWidok | null>(
    poczatkowa?.kontrahent_id
      ? { id: poczatkowa.kontrahent_id, nazwa: poczatkowa.nabywca_nazwa, nip: poczatkowa.nabywca_nip,
          adres: adresKontrahenta({ adres_ulica: poczatkowa.nabywca_adres_ulica, kod_pocztowy: poczatkowa.nabywca_kod_pocztowy, miejscowosc: poczatkowa.nabywca_miejscowosc }),
          termin: null }
      : null,
  )
  const [szukanyNabywca, setSzukanyNabywca] = useState('')
  const [wiersze, setWiersze] = useState<Wiersz[]>(() =>
    poczatkowa?.pozycje.length
      ? poczatkowa.pozycje.map((p) => ({ klucz: ++licznikWierszy, towar_id: p.towar_id, nazwa: p.nazwa, jm: p.jm,
          ilosc: naIlosc(p.ilosc), cena: naZlote(p.cena_netto), stawka_vat_kod: p.stawka_vat_kod, gtu: p.gtu }))
      : [nowyWiersz()],
  )
  // Termin wpisany ręcznie (albo zapisany w szkicu) nie jest już przeliczany automatycznie.
  const [terminReczny, setTerminReczny] = useState(poczatkowa !== null)
  const [blad, setBlad] = useState<string | null>(null)
  const [potwierdzenie, setPotwierdzenie] = useState<'zatwierdz' | 'usun' | null>(null)
  const [braki, setBraki] = useState<string[]>(poczatkowa?.braki ?? [])

  const seriaFaktur = (serie.data ?? []).filter((s) => s.typ_dokumentu === 'faktura_sprzedazy' && (s.aktywna || s.id === nagl.seria_id))
  const aktywneKonta = (konta.data ?? []).filter((k) => k.aktywne || k.id === nagl.konto_bankowe_id)
  const uzyteStawki = new Set(poczatkowa?.pozycje.map((p) => p.stawka_vat_kod))
  const dostepneStawki = (stawki.data ?? []).filter((s) => s.aktywna || uzyteStawki.has(s.kod))
  const domyslnaStawka = stawki.data?.find((s) => s.domyslna)?.kod ?? ''

  // Nowa faktura: domyślne wartości z Ustawień, gdy tylko się wczytają (raz).
  const wypelnione = useRef(poczatkowa !== null)
  useEffect(() => {
    if (wypelnione.current || !firma.data || !serie.data || !konta.data || !stawki.data) return
    wypelnione.current = true
    const f = firma.data
    setNagl((n) => ({
      ...n,
      seria_id: seriaFaktur.find((s) => s.aktywna)?.id ?? null,
      forma_platnosci: f.forma_platnosci,
      miejsce_wystawienia: f.miejsce_wystawienia,
      wystawiajacy: f.wystawiajacy,
      uwagi: f.uwagi_na_fakturze,
      konto_bankowe_id: konta.data.find((k) => k.domyslne && k.aktywne && k.waluta === 'PLN')?.id ?? null,
    }))
    setWiersze((w) => w.map((x) => (x.stawka_vat_kod ? x : { ...x, stawka_vat_kod: domyslnaStawka })))
  }, [firma.data, serie.data, konta.data, stawki.data]) // eslint-disable-line react-hooks/exhaustive-deps

  // Termin płatności: gotówka/karta — dzień wystawienia; przelew — termin kontrahenta albo domyślny z Ustawień.
  useEffect(() => {
    if (terminReczny) return
    const dni = nagl.forma_platnosci === 'przelew' ? (nabywca?.termin ?? firma.data?.termin_platnosci_dni ?? 14) : 0
    setNagl((n) => ({ ...n, termin_platnosci: dodajDni(n.data_wystawienia, dni) }))
  }, [terminReczny, nagl.forma_platnosci, nagl.data_wystawienia, nabywca, firma.data])

  const ustaw = <K extends keyof typeof nagl>(pole: K, w: (typeof nagl)[K]) => setNagl((n) => ({ ...n, [pole]: w }))
  const ustawWiersz = (klucz: number, zmiana: Partial<Wiersz>) =>
    setWiersze((ws) => ws.map((w) => (w.klucz === klucz ? { ...w, ...zmiana } : w)))

  // Podsumowanie na żywo — te same zasady co na serwerze (VAT od sumy netto w stawce).
  const podsumowanie = useMemo(() => {
    const procenty = new Map((stawki.data ?? []).map((s) => [s.kod, s]))
    const wartosci = new Map<number, number | null>()
    const netto = new Map<string, number>()
    for (const w of wiersze) {
      const il = normalizujIlosc(w.ilosc)
      const cena = naGrosze(w.cena)
      const wartosc = il !== undefined && typeof cena === 'number' ? wartoscPozycji(il, cena) : null
      wartosci.set(w.klucz, wartosc)
      if (wartosc !== null && w.stawka_vat_kod) netto.set(w.stawka_vat_kod, (netto.get(w.stawka_vat_kod) ?? 0) + wartosc)
    }
    const wgStawek = [...netto.entries()]
      .map(([kod, n]) => ({ kod, nazwa: procenty.get(kod)?.nazwa ?? kod, kolej: procenty.get(kod) ? [...procenty.keys()].indexOf(kod) : 99, netto: n, vat: vatOdNetto(n, procenty.get(kod)?.procent ?? null) }))
      .sort((a, b) => a.kolej - b.kolej)
    const sumaNetto = wgStawek.reduce((s, x) => s + x.netto, 0)
    const sumaVat = wgStawek.reduce((s, x) => s + x.vat, 0)
    return { wartosci, wgStawek, netto: sumaNetto, vat: sumaVat, brutto: sumaNetto + sumaVat }
  }, [wiersze, stawki.data])

  const zbudujDane = (): FakturaDane | string => {
    const pozycje: FakturaDane['pozycje'] = []
    for (const [i, w] of wiersze.entries()) {
      if (!w.nazwa.trim() && !w.cena.trim()) continue // pusty wiersz pomijamy
      const nr = i + 1
      const ilosc = normalizujIlosc(w.ilosc)
      const cena = naGrosze(w.cena)
      if (!w.nazwa.trim()) return `Pozycja ${nr}: podaj nazwę`
      if (ilosc === undefined) return `Pozycja ${nr}: ilość musi być dodatnia, najwyżej 4 miejsca po przecinku`
      if (typeof cena !== 'number') return `Pozycja ${nr}: wpisz cenę netto, np. 12,50`
      if (!w.stawka_vat_kod) return `Pozycja ${nr}: wybierz stawkę VAT`
      pozycje.push({ towar_id: w.towar_id, nazwa: w.nazwa.trim(), jm: w.jm.trim() || 'szt.', ilosc, cena_netto: cena, stawka_vat_kod: w.stawka_vat_kod, gtu: w.gtu })
    }
    return { ...nagl, kontrahent_id: nabywca?.id ?? null, pozycje }
  }

  const zapiszSzkic = (potem?: (f: Faktura) => void) => {
    const dane = zbudujDane()
    if (typeof dane === 'string') return setBlad(dane)
    setBlad(null)
    zapisz.mutate({ id: poczatkowa?.id ?? null, dane }, {
      onSuccess: (f) => { setBraki(f.braki); if (potem) potem(f); else onZamknij() },
      onError: (e) => setBlad(e.message),
    })
  }
  const naWyslanie = (e: FormEvent) => { e.preventDefault(); zapiszSzkic() }
  const zatwierdzTeraz = () =>
    zapiszSzkic((f) => {
      onZapisano(f.id)
      if (f.braki.length) { setPotwierdzenie(null); return setBlad('Faktura zapisana jako szkic, ale nie da się jej jeszcze zatwierdzić.') }
      zatwierdz.mutate(f.id, { onError: (e) => { setPotwierdzenie(null); setBlad(e.message) } })
    })

  const zajety = zapisz.isPending || zatwierdz.isPending || usun.isPending
  const nowy = poczatkowa === null
  const tytulOkna = nowy ? 'Nowa faktura VAT' : 'Szkic faktury'

  return (
    <Panel
      szerokie
      tytul={tytulOkna}
      naglowekDodatek={<Plakietka ton="zloty">Szkic</Plakietka>}
      opis="Numer zostanie nadany przy zatwierdzeniu. Szkic można dowolnie zmieniać."
      onZamknij={onZamknij}
      blad={blad}
      stopka={
        potwierdzenie === 'zatwierdz' ? (
          <>
            <span className="mr-auto flex items-center gap-2 text-sm font-medium text-marka-900">
              <FileCheck2 className="size-4 text-zloto-600" /> Po zatwierdzeniu faktura dostanie numer i nie będzie można jej zmienić.
            </span>
            <Przycisk laduje={zajety} onClick={zatwierdzTeraz}>Tak, zatwierdź</Przycisk>
            <Przycisk wariant="cichy" onClick={() => setPotwierdzenie(null)}>Wróć</Przycisk>
          </>
        ) : potwierdzenie === 'usun' ? (
          <>
            <span className="mr-auto text-sm font-medium text-blad">Usunąć ten szkic? Tego nie da się cofnąć.</span>
            <Przycisk laduje={usun.isPending} className="!bg-blad hover:!bg-blad/90" onClick={() => poczatkowa && usun.mutate(poczatkowa.id, { onSuccess: onZamknij, onError: (e) => setBlad(e.message) })}>Usuń szkic</Przycisk>
            <Przycisk wariant="cichy" onClick={() => setPotwierdzenie(null)}>Wróć</Przycisk>
          </>
        ) : (
          <>
            <Przycisk onClick={() => setPotwierdzenie('zatwierdz')} disabled={zajety}><CheckCircle2 className="size-4" /> Zatwierdź</Przycisk>
            <Przycisk type="submit" form="formularz-faktury" wariant="drugorzedny" laduje={zapisz.isPending}>Zapisz szkic</Przycisk>
            <Przycisk wariant="cichy" onClick={onZamknij}>Zamknij</Przycisk>
            {!nowy && <Przycisk wariant="cichy" className="ml-auto !text-blad" onClick={() => setPotwierdzenie('usun')}><Trash2 className="size-4" /> Usuń szkic</Przycisk>}
          </>
        )
      }
    >
      <form id="formularz-faktury" onSubmit={naWyslanie}>
        {braki.length > 0 && !nowy && (
          <div className="mb-5 rounded-lg border border-ostrzezenie/20 bg-ostrzezenie-tlo px-4 py-3 text-sm text-ostrzezenie">
            <p className="flex items-center gap-2 font-medium"><AlertTriangle className="size-4" /> Przed zatwierdzeniem:</p>
            <ul className="mt-1 list-inside list-disc pl-6">{braki.map((b) => <li key={b}>{b}</li>)}</ul>
          </div>
        )}

        <SekcjaFormularza tytul="Nabywca">
          <div className="sm:col-span-6">
            {nabywca ? (
              <div className="flex items-start justify-between gap-3 rounded-lg border border-marka-200 bg-marka-50/50 px-4 py-3">
                <div className="min-w-0 text-sm">
                  <p className="font-semibold text-marka-950">{nabywca.nazwa}</p>
                  <p className="text-tekst-drugorzedny">{[nabywca.nip && `NIP ${nabywca.nip}`, nabywca.adres].filter(Boolean).join(' · ') || '—'}</p>
                </div>
                <Przycisk wariant="cichy" className="!px-2" aria-label="Zmień nabywcę" onClick={() => { setNabywca(null); setSzukanyNabywca('') }}><X className="size-4" /></Przycisk>
              </div>
            ) : (
              <Podpowiedzi<Kontrahent>
                klucz="odbiorcy" etykieta="Szukaj nabywcy" placeholder="Zacznij pisać nazwę, NIP albo miejscowość odbiorcy…"
                wartosc={szukanyNabywca} onZmiana={setSzukanyNabywca} szukaj={szukajKontrahentow}
                onWybierz={(k) => setNabywca({ id: k.id, nazwa: k.nazwa, nip: k.nip, adres: adresKontrahenta(k), termin: k.termin_platnosci_dni })}
                pokaz={(k) => (
                  <span className="flex flex-col">
                    <span className="font-medium">{k.nazwa}{!k.aktywny && <span className="ml-2 text-xs text-neutral-400">(wyłączony)</span>}</span>
                    <span className="text-xs text-neutral-500">{[k.nip && `NIP ${k.nip}`, k.miejscowosc].filter(Boolean).join(' · ')}</span>
                  </span>
                )}
              />
            )}
          </div>
        </SekcjaFormularza>

        <SekcjaFormularza tytul="Dokument">
          <Pole etykieta="Seria numeracji" className="sm:col-span-2" podpowiedz={seriaFaktur.length === 0 ? 'Dodaj serię w Ustawieniach → Faktury' : undefined}>
            <Wybor value={nagl.seria_id ?? ''} onChange={(e) => ustaw('seria_id', e.target.value ? Number(e.target.value) : null)}>
              <option value="">— wybierz —</option>
              {seriaFaktur.map((s) => <option key={s.id} value={s.id}>{s.nazwa} ({s.przyklad})</option>)}
            </Wybor>
          </Pole>
          <Pole etykieta="Data wystawienia" className="sm:col-span-2">
            <Wejscie type="date" required value={nagl.data_wystawienia} onChange={(e) => ustaw('data_wystawienia', e.target.value)} />
          </Pole>
          <Pole etykieta="Data sprzedaży" className="sm:col-span-2" podpowiedz="Dostawy towaru / wykonania usługi">
            <Wejscie type="date" required value={nagl.data_sprzedazy} onChange={(e) => ustaw('data_sprzedazy', e.target.value)} />
          </Pole>
        </SekcjaFormularza>

        <fieldset className="mb-6">
          <legend className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">Pozycje</legend>
          <div className="overflow-x-auto rounded-lg border border-obramowanie">
            <table className="w-full min-w-200 text-sm">
              <thead>
                <tr className="border-b border-obramowanie bg-neutral-50/70 text-left text-xs uppercase tracking-wider text-neutral-500">
                  <th className="w-8 py-2 pl-3 font-medium">Lp</th>
                  <th className="px-2 py-2 font-medium">Nazwa towaru lub usługi</th>
                  <th className="w-24 px-2 py-2 text-right font-medium">Ilość</th>
                  <th className="w-20 px-2 py-2 font-medium">J.m.</th>
                  <th className="w-28 px-2 py-2 text-right font-medium">Cena netto</th>
                  <th className="w-32 px-2 py-2 font-medium">VAT</th>
                  <th className="w-28 px-2 py-2 text-right font-medium">Wartość netto</th>
                  <th className="w-9" />
                </tr>
              </thead>
              <tbody className="divide-y divide-obramowanie">
                {wiersze.map((w, i) => {
                  const wartosc = podsumowanie.wartosci.get(w.klucz)
                  return (
                    <tr key={w.klucz} className="align-top">
                      <td className="liczby py-3.5 pl-3 text-neutral-500">{i + 1}</td>
                      <td className="px-2 py-2">
                        <Podpowiedzi<Towar>
                          klucz="towary" etykieta={`Nazwa pozycji ${i + 1}`} placeholder="Nazwa albo symbol z kartoteki…"
                          wartosc={w.nazwa} onZmiana={(t) => ustawWiersz(w.klucz, { nazwa: t, towar_id: null })} szukaj={szukajTowarow}
                          onWybierz={(t) => ustawWiersz(w.klucz, {
                            towar_id: t.id, nazwa: t.nazwa, jm: t.jm, gtu: t.gtu,
                            stawka_vat_kod: dostepneStawki.some((s) => s.kod === t.stawka_vat_kod) ? t.stawka_vat_kod : domyslnaStawka,
                            cena: t.cena_sprzedazy_netto === null ? w.cena : naZlote(t.cena_sprzedazy_netto),
                          })}
                          pokaz={(t) => (
                            <span className="flex items-center justify-between gap-3">
                              <span className="min-w-0"><span className="mr-2 font-mono text-xs text-neutral-500">{t.symbol}</span>{t.nazwa}</span>
                              {t.cena_sprzedazy_netto !== null && <span className="liczby shrink-0 text-xs text-neutral-500">{naZlote(t.cena_sprzedazy_netto)} zł</span>}
                            </span>
                          )}
                        />
                        {w.towar_id !== null && <span className="mt-1 block text-xs text-marka-700">z kartoteki</span>}
                      </td>
                      <td className="px-2 py-2"><Wejscie aria-label={`Ilość, pozycja ${i + 1}`} inputMode="decimal" value={w.ilosc} onChange={(e) => ustawWiersz(w.klucz, { ilosc: e.target.value })} className="liczby text-right" /></td>
                      <td className="px-2 py-2"><Wejscie aria-label={`Jednostka, pozycja ${i + 1}`} value={w.jm} maxLength={10} onChange={(e) => ustawWiersz(w.klucz, { jm: e.target.value })} /></td>
                      <td className="px-2 py-2"><Wejscie aria-label={`Cena netto, pozycja ${i + 1}`} inputMode="decimal" placeholder="0,00" value={w.cena} onChange={(e) => ustawWiersz(w.klucz, { cena: e.target.value })} className="liczby text-right" /></td>
                      <td className="px-2 py-2">
                        <Wybor aria-label={`Stawka VAT, pozycja ${i + 1}`} value={w.stawka_vat_kod} onChange={(e) => ustawWiersz(w.klucz, { stawka_vat_kod: e.target.value })}>
                          <option value="">—</option>
                          {dostepneStawki.map((s) => <option key={s.kod} value={s.kod}>{s.kod === 'zw' || s.procent === null ? s.kod : `${s.procent}%`}{s.kod.includes(' ') ? ` (${s.kod.split(' ')[1]})` : ''}</option>)}
                        </Wybor>
                      </td>
                      <td className="liczby px-2 py-3.5 text-right font-medium">{wartosc == null ? <span className="text-neutral-300">—</span> : naZlote(wartosc)}</td>
                      <td className="py-2 pr-2">
                        <button type="button" aria-label={`Usuń pozycję ${i + 1}`} disabled={wiersze.length === 1}
                          onClick={() => setWiersze((ws) => ws.filter((x) => x.klucz !== w.klucz))}
                          className="mt-1 rounded-md p-1.5 text-neutral-400 transition hover:bg-blad-tlo hover:text-blad disabled:invisible">
                          <Trash2 className="size-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Przycisk wariant="cichy" className="mt-2" onClick={() => setWiersze((ws) => [...ws, nowyWiersz(domyslnaStawka)])}><Plus className="size-4" /> Dodaj pozycję</Przycisk>
        </fieldset>

        <div className="mb-6 grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <SekcjaFormularza tytul="Płatność">
              <Pole etykieta="Forma płatności" className="sm:col-span-3">
                <Wybor value={nagl.forma_platnosci} onChange={(e) => ustaw('forma_platnosci', e.target.value as FormaPlatnosci)}>
                  {(Object.keys(FORMY_PLATNOSCI) as FormaPlatnosci[]).map((f) => <option key={f} value={f}>{FORMY_PLATNOSCI[f]}</option>)}
                </Wybor>
              </Pole>
              <Pole etykieta="Termin płatności" className="sm:col-span-3" podpowiedz={terminReczny ? undefined : 'Liczony automatycznie'}>
                <Wejscie type="date" min={nagl.data_wystawienia} value={nagl.termin_platnosci ?? ''} onChange={(e) => { setTerminReczny(true); ustaw('termin_platnosci', e.target.value || null) }} />
              </Pole>
              {nagl.forma_platnosci === 'przelew' && (
                <Pole etykieta="Konto do przelewu" className="sm:col-span-6" podpowiedz={aktywneKonta.length === 0 ? 'Dodaj konto w Ustawieniach → Konta bankowe' : undefined}>
                  <Wybor value={nagl.konto_bankowe_id ?? ''} onChange={(e) => ustaw('konto_bankowe_id', e.target.value ? Number(e.target.value) : null)}>
                    <option value="">Domyślne konto PLN</option>
                    {aktywneKonta.map((k) => <option key={k.id} value={k.id}>{k.nazwa} — {k.numer_sformatowany}</option>)}
                  </Wybor>
                </Pole>
              )}
            </SekcjaFormularza>
          </div>
          <Podsumowanie wgStawek={podsumowanie.wgStawek} netto={podsumowanie.netto} vat={podsumowanie.vat} brutto={podsumowanie.brutto} />
        </div>

        <SekcjaFormularza tytul="Dodatkowe">
          <Pole etykieta="Miejsce wystawienia" className="sm:col-span-3"><Wejscie value={nagl.miejsce_wystawienia} onChange={(e) => ustaw('miejsce_wystawienia', e.target.value)} /></Pole>
          <Pole etykieta="Wystawił(a)" className="sm:col-span-3"><Wejscie value={nagl.wystawiajacy} onChange={(e) => ustaw('wystawiajacy', e.target.value)} /></Pole>
          <Pole etykieta="Uwagi na fakturze" className="sm:col-span-6"><PoleTekstowe rows={2} value={nagl.uwagi} onChange={(e) => ustaw('uwagi', e.target.value)} /></Pole>
        </SekcjaFormularza>
      </form>
    </Panel>
  )
}

function Podsumowanie({ wgStawek, netto, vat, brutto }: {
  wgStawek: { kod: string; nazwa: string; netto: number; vat: number }[]
  netto: number
  vat: number
  brutto: number
}) {
  return (
    <div className="self-start rounded-xl bg-marka-950 p-5 text-white lg:col-span-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-marka-300">
            <th className="pb-2 font-medium">Stawka</th>
            <th className="pb-2 text-right font-medium">Netto</th>
            <th className="pb-2 text-right font-medium">VAT</th>
          </tr>
        </thead>
        <tbody>
          {wgStawek.length === 0 && <tr><td colSpan={3} className="py-1 text-marka-300">Brak pozycji</td></tr>}
          {wgStawek.map((s) => (
            <tr key={s.kod} className="text-marka-100">
              <td className="py-0.5">{s.nazwa}</td>
              <td className="liczby py-0.5 text-right">{naZlote(s.netto)}</td>
              <td className="liczby py-0.5 text-right">{naZlote(s.vat)}</td>
            </tr>
          ))}
          <tr className="border-t border-white/15 text-marka-100">
            <td className="pt-2">Razem</td>
            <td className="liczby pt-2 text-right">{naZlote(netto)}</td>
            <td className="liczby pt-2 text-right">{naZlote(vat)}</td>
          </tr>
        </tbody>
      </table>
      <div className="mt-4 flex items-baseline justify-between border-t border-white/15 pt-4">
        <span className="text-sm text-marka-200">Do zapłaty</span>
        <span className="liczby text-2xl font-semibold tracking-tight text-zloto-300">{naZlote(brutto)} <span className="text-base font-medium">zł</span></span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- Podgląd zatwierdzonej / anulowanej

function PodgladFaktury({ f, onZamknij }: { f: Faktura; onZamknij: () => void }) {
  const anuluj = useAnulujFakture()
  const [anulowanie, setAnulowanie] = useState(false)
  const [przyczyna, setPrzyczyna] = useState('')
  const s = f.sprzedawca ?? {}
  const tekst = (k: string) => String((s as Record<string, unknown>)[k] ?? '')

  return (
    <Panel
      szerokie
      tytul={`Faktura VAT ${f.numer}`}
      naglowekDodatek={<Plakietka ton={TON_STATUSU[f.status]}>{STATUSY[f.status]}</Plakietka>}
      opis={`Zatwierdzona ${f.zatwierdzono ? new Date(f.zatwierdzono).toLocaleString('pl-PL') : ''}. Zmiana tylko przez korektę lub anulowanie.`}
      onZamknij={onZamknij}
      blad={anuluj.error?.message}
      stopka={
        anulowanie ? (
          <form className="flex w-full flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); anuluj.mutate({ id: f.id, przyczyna }, { onSuccess: () => setAnulowanie(false) }) }}>
            <Wejscie autoFocus required placeholder="Przyczyna anulowania (trafi do dziennika)" value={przyczyna} onChange={(e) => setPrzyczyna(e.target.value)} className="min-w-64 flex-1" />
            <Przycisk type="submit" laduje={anuluj.isPending} className="!bg-blad hover:!bg-blad/90">Anuluj fakturę</Przycisk>
            <Przycisk wariant="cichy" onClick={() => setAnulowanie(false)}>Wróć</Przycisk>
          </form>
        ) : (
          <>
            <Przycisk wariant="drugorzedny" onClick={onZamknij}>Zamknij</Przycisk>
            <span className="text-xs text-neutral-500">Wydruk PDF — w kolejnym kroku.</span>
            {f.status === 'zatwierdzony' && (
              <Przycisk wariant="cichy" className="ml-auto !text-blad" onClick={() => setAnulowanie(true)}><Ban className="size-4" /> Anuluj fakturę</Przycisk>
            )}
          </>
        )
      }
    >
      <div className="mb-5 flex items-center gap-2 rounded-lg border border-zloto-200 bg-zloto-50 px-4 py-2 text-xs font-medium text-zloto-800">
        <AlertTriangle className="size-4 shrink-0" /> Dokument testowy — nie jest fakturą. Obowiązujące faktury wystawia Fakturownia do czasu podłączenia KSeF.
      </div>
      {f.status === 'anulowany' && (
        <div className="mb-5"><Komunikat rodzaj="blad">Anulowana {f.anulowano ? new Date(f.anulowano).toLocaleString('pl-PL') : ''}. Przyczyna: {f.przyczyna_anulowania}</Komunikat></div>
      )}

      <div className={`grid gap-6 sm:grid-cols-2 ${f.status === 'anulowany' ? 'opacity-60' : ''}`}>
        <Strona tytul="Sprzedawca" linie={[tekst('nazwa'), tekst('nip') && `NIP ${tekst('nip')}`, tekst('adres_ulica'), `${tekst('kod_pocztowy')} ${tekst('miejscowosc')}`.trim()]} />
        <Strona tytul="Nabywca" linie={[f.nabywca_nazwa, f.nabywca_nip && `NIP ${f.nabywca_nip}`, f.nabywca_adres_ulica, `${f.nabywca_kod_pocztowy} ${f.nabywca_miejscowosc}`.trim()]} />
      </div>

      <dl className="my-6 grid grid-cols-2 gap-4 rounded-lg bg-neutral-50 px-4 py-3 text-sm sm:grid-cols-4">
        <Dana etykieta="Data wystawienia" wartosc={naDate(f.data_wystawienia)} />
        <Dana etykieta="Data sprzedaży" wartosc={naDate(f.data_sprzedazy)} />
        <Dana etykieta="Płatność" wartosc={FORMY_PLATNOSCI[f.forma_platnosci]} />
        <Dana etykieta="Termin" wartosc={naDate(f.termin_platnosci)} />
      </dl>

      <div className="overflow-x-auto rounded-lg border border-obramowanie">
        <table className="w-full min-w-176 text-sm">
          <thead>
            <tr className="border-b border-obramowanie bg-neutral-50/70 text-left text-xs uppercase tracking-wider text-neutral-500">
              <th className="py-2 pl-4 font-medium">Lp</th>
              <th className="px-3 py-2 font-medium">Nazwa</th>
              <th className="px-3 py-2 text-right font-medium">Ilość</th>
              <th className="px-3 py-2 text-right font-medium">Cena netto</th>
              <th className="px-3 py-2 text-right font-medium">VAT</th>
              <th className="py-2 pr-4 text-right font-medium">Wartość netto</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-obramowanie">
            {f.pozycje.map((p) => (
              <tr key={p.lp}>
                <td className="liczby py-2.5 pl-4 text-neutral-500">{p.lp}</td>
                <td className="px-3 py-2.5">{p.nazwa}{p.gtu && <span className="ml-2 text-xs text-neutral-500">{p.gtu}</span>}</td>
                <td className="liczby px-3 py-2.5 text-right">{naIlosc(p.ilosc)} {p.jm}</td>
                <td className="liczby px-3 py-2.5 text-right">{naZlote(p.cena_netto)}</td>
                <td className="liczby px-3 py-2.5 text-right">{p.stawka_vat_kod}{/^\d+$/.test(p.stawka_vat_kod) ? '%' : ''}</td>
                <td className="liczby py-2.5 pr-4 text-right font-medium">{naZlote(p.wartosc_netto)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <div className="space-y-3 text-sm lg:col-span-3">
          {f.forma_platnosci === 'przelew' && f.sprzedawca?.konto && (
            <p><span className="text-neutral-500">Konto: </span><span className="liczby font-mono">{naIban(f.sprzedawca.konto.numer)}</span>{f.sprzedawca.konto.bank && <span className="text-neutral-500"> ({f.sprzedawca.konto.bank})</span>}</p>
          )}
          {f.miejsce_wystawienia && <p><span className="text-neutral-500">Miejsce wystawienia: </span>{f.miejsce_wystawienia}</p>}
          {f.wystawiajacy && <p><span className="text-neutral-500">Wystawił(a): </span>{f.wystawiajacy}</p>}
          {f.uwagi && <p className="whitespace-pre-line rounded-lg bg-neutral-50 px-3 py-2">{f.uwagi}</p>}
        </div>
        <Podsumowanie wgStawek={f.stawki} netto={f.suma_netto} vat={f.suma_vat} brutto={f.suma_brutto} />
      </div>
    </Panel>
  )
}

function Strona({ tytul, linie }: { tytul: string; linie: (string | false)[] }) {
  return (
    <div>
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-neutral-500">{tytul}</h3>
      {linie.filter(Boolean).map((l, i) => <p key={i} className={i === 0 ? 'font-semibold text-marka-950' : 'text-sm text-tekst-drugorzedny'}>{l}</p>)}
    </div>
  )
}

function Dana({ etykieta, wartosc }: { etykieta: string; wartosc: string }) {
  return (
    <div>
      <dt className="text-xs text-neutral-500">{etykieta}</dt>
      <dd className="liczby font-medium text-marka-950">{wartosc}</dd>
    </div>
  )
}
