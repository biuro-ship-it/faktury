import {
  Banknote,
  BookUser,
  ChartColumn,
  Factory,
  FileText,
  LayoutDashboard,
  type LucideIcon,
  MessageSquareText,
  ReceiptText,
  Scale,
  ShoppingCart,
  Warehouse,
} from 'lucide-react'

export type Modul = {
  sciezka: string
  nazwa: string
  ikona: LucideIcon
  faza: number
  opis: string
  zakres: string[]
}

export const PULPIT = { sciezka: '/', nazwa: 'Pulpit', ikona: LayoutDashboard }
export const UWAGI = { sciezka: '/uwagi', nazwa: 'Uwagi', ikona: MessageSquareText }

// Kolejność i zakres wg PLAN.md (sekcje 1 i 6).
export const MODULY: Modul[] = [
  {
    sciezka: '/kartoteki', nazwa: 'Kartoteki', ikona: BookUser, faza: 1,
    opis: 'Kontrahenci, towary, magazyny i receptury — dane, na których opierają się dokumenty.',
    zakres: ['Kontrahenci z danymi z Białej Listy MF (po NIP)', 'Towary, surowce, wyroby i usługi', 'Magazyny i kategorie kosztów', 'Receptury wyrobów', 'Import CSV'],
  },
  {
    sciezka: '/sprzedaz', nazwa: 'Sprzedaż', ikona: FileText, faza: 2,
    opis: 'Faktury sprzedaży, korekty i proformy ze wszystkimi skutkami w jednej transakcji.',
    zakres: ['Faktura VAT, korekta, proforma', 'Szkic → zatwierdzenie → anulowanie', 'PDF faktury', 'Rejestr sprzedaży z sumami po stawkach VAT'],
  },
  {
    sciezka: '/zakupy', nazwa: 'Zakupy', ikona: ShoppingCart, faza: 2,
    opis: 'Faktury zakupu towarów i surowców z automatycznym przyjęciem na magazyn (PZ).',
    zakres: ['Faktura zakupu → automatyczne PZ', 'Rejestr zakupów'],
  },
  {
    sciezka: '/koszty', nazwa: 'Koszty', ikona: ReceiptText, faza: 2,
    opis: 'Faktury kosztowe bez ruchu magazynowego — media, paliwo, usługi.',
    zakres: ['Faktura kosztowa z kategorią kosztu', 'Import XML FA(3) z KSeF (opcjonalnie)'],
  },
  {
    sciezka: '/kasa', nazwa: 'Kasa', ikona: Banknote, faza: 3,
    opis: 'Dowody KP i KW, raporty kasowe i bieżący stan kasy.',
    zakres: ['KP / KW', 'Raport kasowy dzienny i miesięczny', 'Stan kasy', 'Ręczne zapisy bankowe'],
  },
  {
    sciezka: '/magazyn', nazwa: 'Magazyn', ikona: Warehouse, faza: 4,
    opis: 'Dokumenty magazynowe, partie i wycena FIFO.',
    zakres: ['BO, PZ, WZ, RW, PW, MM', 'Wycena FIFO i stany na dzień', 'Karta towaru', 'Inwentaryzacja'],
  },
  {
    sciezka: '/produkcja', nazwa: 'Produkcja', ikona: Factory, faza: 5,
    opis: 'Zlecenia produkcyjne na podstawie receptur: zużycie surowców i przyjęcie wyrobu.',
    zakres: ['Zlecenie produkcyjne → RW surowców + PW wyrobu', 'Sprawdzenie dostępności surowców', 'Koszt jednostkowy wyrobu'],
  },
  {
    sciezka: '/rozrachunki', nazwa: 'Rozrachunki', ikona: Scale, faza: 3,
    opis: 'Należności i zobowiązania, rozliczenia, kompensaty i wiekowanie.',
    zakres: ['Należności i zobowiązania z dokumentów', 'Rozliczenia pełne i częściowe, kompensaty', 'Wiekowanie 0–30 / 31–60 / 61–90 / 90+', 'Lista dłużników'],
  },
  {
    sciezka: '/raporty', nazwa: 'Raporty', ikona: ChartColumn, faza: 6,
    opis: 'Sprzedaż, marża, koszty, wartość magazynu i przepływy kasowe.',
    zakres: ['Sprzedaż i marża (koszt FIFO)', 'Koszty wg kategorii', 'Wartość magazynu', 'Eksport CSV / XLSX'],
  },
]
