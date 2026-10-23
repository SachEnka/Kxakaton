export type Role = "CLIENT" | "UNDERWRITER";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  role: Role;
}

export interface ProductCard {
  code: string;
  title: string;
  summary: string;
  min_amount: number;
  max_amount: number;
  min_term: number;
  max_term: number;
  base_rate: number;
  fits: boolean;
  suggested_amount: number;
  suggested_term: number;
  reason: string;
  recommended: boolean;
}

export interface TimelineItem {
  key: string;
  title: string;
  state: "complete" | "current" | "upcoming" | "skipped" | "failed";
}

export interface Decision {
  score: number;
  financial_position_label: string;
  debt_service_label: string;
  quality_category: string;
  decision: string;
  offered_amount: number | null;
  offered_term_months: number | null;
  offered_rate: number | null;
  monthly_payment: number | null;
  explanation: string;
  stop_factors: string[];
  awaits_employee: boolean;
  changes: { field: string; requested: number; offered: number }[];
  model_note: string;
  factors?: { code: string; title: string; detail: string }[];
}

export interface Application {
  id: string;
  public_number: string;
  status: string;
  status_label: string;
  stage: { done: string; now: string; next_actor: string };
  timeline: TimelineItem[];
  purpose_label: string;
  product_name: string;
  product_code: string;
  amount: number;
  term_months: number;
  monthly_revenue: number | null;
  monthly_expenses: number | null;
  comment: string;
  created_at: string;
  awaits_employee: boolean;
  company: {
    inn: string | null;
    name: string | null;
    full_name?: string | null;
    legal_form: string | null;
    ogrn: string | null;
    kpp?: string | null;
    registry_status: string | null;
    registry_status_label?: string | null;
    director_name: string | null;
    address: string | null;
    region?: string | null;
    registration_date: string | null;
    source_label?: string | null;
  };
  events: { id: string; actor_type: string; message: string; created_at: string; to_status: string }[];
  decision: Decision | null;
  pending_question: string | null;
  contract_status: string | null;
  checks?: { id: string; source: string; status: string; response: unknown }[];
  scores?: { id: string; score: number; quality_category: string; decision: string; explanation: string; created_at: string }[];
}

export interface Brief {
  id: string;
  public_number: string;
  status: string;
  status_label: string;
  company_name: string | null;
  inn: string | null;
  product_name: string;
  amount: number;
  created_at: string;
  awaits_employee: boolean;
}

const TOKEN_KEY = "credit-token";
const USER_KEY = "credit-user";

export function loadUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function saveSession(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function errorText(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "Не удалось выполнить запрос";
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (typeof item?.msg === "string" ? item.msg : "Проверьте поля")).join(". ");
  }
  return "Не удалось выполнить запрос";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (response.status === 401 && !path.includes("/auth/login") && !path.includes("/auth/register")) {
    clearSession();
    window.location.assign("/login");
  }
  if (!response.ok) throw new Error(errorText(payload));
  return payload as T;
}
