import { Star } from 'lucide-react'
import { useProfil } from '../auth/AuthProvider'
import { Karta, Przelacznik, Przycisk } from '../ui/formularz'
import { useStawki, useZmienStawke } from './api'

export function ZakladkaStawki() {
  const admin = useProfil().rola === 'admin'
  const stawki = useStawki()
  const zmien = useZmienStawke()

  return (
    <Karta
      tytul="Stawki VAT"
      opis="Kody zgodne z polem P_12 schemy FA(3) (KSeF). Stawek się nie usuwa — nieużywane wyłącz, żeby nie zaśmiecały list."
    >
      {zmien.isError && <p className="mb-3 text-sm text-blad">{zmien.error.message}</p>}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-obramowanie text-left text-xs uppercase tracking-wider text-neutral-500">
            <th className="py-2 pr-4 font-medium">Kod FA(3)</th>
            <th className="py-2 pr-4 font-medium">Nazwa</th>
            <th className="py-2 pr-4 text-right font-medium">Stawka</th>
            <th className="py-2 pr-4 font-medium">Domyślna</th>
            <th className="py-2 font-medium">Aktywna</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-obramowanie">
          {stawki.data?.map((s) => (
            <tr key={s.kod} className={s.aktywna ? '' : 'text-neutral-400'}>
              <td className="py-2.5 pr-4 font-mono text-xs">{s.kod}</td>
              <td className="py-2.5 pr-4">{s.nazwa}</td>
              <td className="py-2.5 pr-4 text-right">{s.procent === null ? '—' : `${s.procent}%`}</td>
              <td className="py-2.5 pr-4">
                {s.domyslna ? (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-zloto-800">
                    <Star className="size-3.5 fill-zloto-500 text-zloto-600" /> domyślna
                  </span>
                ) : (
                  admin && s.aktywna && (
                    <Przycisk wariant="cichy" className="!px-2 !py-1 text-xs" onClick={() => zmien.mutate({ kod: s.kod, domyslna: true })}>
                      ustaw
                    </Przycisk>
                  )
                )}
              </td>
              <td className="py-2.5">
                <Przelacznik etykieta={`Stawka ${s.kod} aktywna`} wlaczony={s.aktywna} disabled={!admin || s.domyslna || zmien.isPending}
                  onZmiana={(v) => zmien.mutate({ kod: s.kod, aktywna: v })} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Karta>
  )
}
