import { Landmark, type LucideIcon, ShoppingBag, Users } from 'lucide-react'

type Integracja = { nazwa: string; ikona: LucideIcon; opis: string; zakres: string[]; kiedy: string }

const INTEGRACJE: Integracja[] = [
  {
    nazwa: 'KSeF — Krajowy System e-Faktur',
    ikona: Landmark,
    opis: 'Wysyłka faktur sprzedaży do KSeF i pobieranie faktur kosztowych.',
    zakres: ['Wysyłka FA(3), statusy i UPO', 'Numer KSeF na fakturze', 'Pobieranie faktur zakupowych do szkiców', 'Tryb offline'],
    kiedy: 'Faza 8',
  },
  {
    nazwa: 'CRM Antyramy / Pluszek',
    ikona: Users,
    opis: 'Wspólna baza kontrahentów z crm.pluszek.pl.',
    zakres: ['Import i synchronizacja kontrahentów', 'Podgląd faktur i należności klienta w CRM'],
    kiedy: 'Po fazie 3',
  },
  {
    nazwa: 'WooCommerce',
    ikona: ShoppingBag,
    opis: 'Zamówienia ze sklepu internetowego jako szkice dokumentów sprzedaży.',
    zakres: ['Pobieranie zamówień', 'Szkic faktury / paragonu z zamówienia', 'Zdjęcie towaru ze stanu magazynu'],
    kiedy: 'Po fazie 4',
  },
]

export function ZakladkaIntegracje() {
  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-tekst-drugorzedny">
        Konfiguracja (klucze API, tokeny, certyfikaty) pojawi się tutaj razem z każdą integracją. Celowo nie zbieramy
        sekretów wcześniej, niż są potrzebne.
      </p>
      <div className="grid gap-4 lg:grid-cols-3">
        {INTEGRACJE.map((i) => (
          <section key={i.nazwa} className="flex flex-col rounded-xl border border-obramowanie bg-powierzchnia p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="grid size-10 place-items-center rounded-lg bg-marka-100 text-marka-800">
                <i.ikona className="size-5" />
              </div>
              <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">{i.kiedy}</span>
            </div>
            <h2 className="mt-4 font-semibold text-marka-950">{i.nazwa}</h2>
            <p className="mt-1 text-sm text-tekst-drugorzedny">{i.opis}</p>
            <ul className="mt-3 space-y-1 text-sm">
              {i.zakres.map((z) => (
                <li key={z} className="flex gap-2">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-marka-400" />
                  {z}
                </li>
              ))}
            </ul>
            <div className="mt-auto pt-4">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-500">
                <span className="size-2 rounded-full bg-neutral-300" /> Nieaktywna
              </span>
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
