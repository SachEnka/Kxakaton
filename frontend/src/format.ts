export function money(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

export function rate(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value)}%`;
}

export function day(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, date] = value.slice(0, 10).split("-");
  if (!year || !month || !date) return value;
  return `${date}.${month}.${year}`;
}

export function when(value: string | null | undefined): string {
  if (!value) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export const PURPOSES = [
  { code: "TURNOVER", title: "Пополнить оборотку", text: "Закупка товара, аренда, текущие расходы" },
  { code: "DEVELOPMENT", title: "Развить дело", text: "Оборудование, ремонт, новое направление" },
  { code: "CASH_GAP", title: "Закрыть кассовый разрыв", text: "Деньги нужны ненадолго" },
  { code: "UNKNOWN", title: "Пока не знаю", text: "Подберём продукт по сумме и сроку" },
] as const;

export interface Preset {
  purpose: string;
  amount: number;
  term: number;
  inn: string;
  legalForm: "OOO" | "IP";
  revenue: number;
  expenses: number;
  title: string;
}

export interface RegistryCard {
  found: boolean;
  source: "demo" | "egrul.nalog.ru";
  source_label: string;
  inn: string;
  short_name: string;
  full_name: string;
  ogrn: string;
  kpp: string;
  legal_form: "OOO" | "IP";
  director_name: string;
  director_post: string;
  region: string;
  address: string;
  registration_date: string | null;
  status: string;
  status_label: string;
  transparent?: {
    address?: string;
    okved?: string;
    charter_capital?: number | null;
    employees_count?: number;
    employees_published?: boolean;
    tax_debt?: boolean;
    tax_debt_amount?: number;
    tax_regime?: string;
    mass_address_count?: number;
    status_name?: string;
    source_label?: string;
    note?: string;
  } | null;
  transparent_error?: string;
  credit_history?: { available: boolean; note: string };
}

export const PRESETS: Record<string, Preset> = {
  "client.good@demo.local": {
    purpose: "TURNOVER",
    amount: 1500000,
    term: 18,
    inn: "7700000001",
    legalForm: "OOO",
    revenue: 800000,
    expenses: 450000,
    title: "Одобрение на запрошенных условиях",
  },
  "client.offer@demo.local": {
    purpose: "TURNOVER",
    amount: 5000000,
    term: 24,
    inn: "7700000002",
    legalForm: "OOO",
    revenue: 400000,
    expenses: 350000,
    title: "Предложение с меньшей суммой",
  },
  "client.reject@demo.local": {
    purpose: "DEVELOPMENT",
    amount: 2000000,
    term: 24,
    inn: "7700000003",
    legalForm: "OOO",
    revenue: 900000,
    expenses: 500000,
    title: "Отказ из-за банкротства",
  },
  "client.info@demo.local": {
    purpose: "TURNOVER",
    amount: 1500000,
    term: 18,
    inn: "7700000005",
    legalForm: "OOO",
    revenue: 350000,
    expenses: 200000,
    title: "Запрос пояснения по молодой компании",
  },
};

export const DEMO_ACCOUNTS = [
  { email: "client.good@demo.local", title: "Клиент: одобрение" },
  { email: "client.offer@demo.local", title: "Клиент: другие условия" },
  { email: "client.reject@demo.local", title: "Клиент: отказ" },
  { email: "client.info@demo.local", title: "Клиент: уточнение" },
  { email: "underwriter@demo.local", title: "Сотрудник банка" },
];
