import axios from 'axios';

/* ─────────────────────────────────────────────────────────────
   Axios instance — points to the FastAPI backend
   ───────────────────────────────────────────────────────────── */
const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
});

/* ─────────────────────────────────────────────────────────────
   Types (mirror the FastAPI Pydantic schemas)
   ───────────────────────────────────────────────────────────── */
export interface OnboardingPayload {
  business_name: string;
  phone_number: string;
  business_hours: Record<string, string>; // e.g. { monday: "09:00-18:00" }
  location: string;
  cancellation_policy: string;
  contact_info: string;
  services: { name: string; price: string; description: string }[];
  faqs?: { question: string; answer: string }[];
  pricing?: string;
  plan?: string;
}

export interface OnboardingResult {
  status: string;
  tenant_id: string;
  phone_number_id: string | null;
  knowledge_fields_ingested: number;
  persona: string | null;
  error: string | null;
  missing_fields: string[] | null;
}

export interface DashboardControlPayload {
  bot_active: boolean;
  system_prompt_override: string;
}

export interface DashboardControlResult {
  status: string;
  message: string;
  tenant_id: string;
  bot_active: boolean;
  system_prompt_override: string | null;
}

export interface LogEntry {
  message_id: string;
  tenant_id: string;
  sender: string;
  channel: string;
  direction: 'inbound' | 'outbound';
  text: string;
  timestamp: string;
}

export interface LogsResult {
  tenant_id: string;
  total: number;
  messages: LogEntry[];
  note: string;
}

export interface PlanLimit {
  limit: number;
  used: number;
  remaining: number;
  unit: string;
}

export interface PlanResult {
  tenant_id: string;
  plan: string;
  limits: Record<string, PlanLimit>;
  note: string;
}

export interface HealthResult {
  status: string;
  version: string;
  service: string;
}

/* ─────────────────────────────────────────────────────────────
   API functions
   ───────────────────────────────────────────────────────────── */

/** POST /api/onboarding — register a new Desk client */
export async function submitOnboarding(data: OnboardingPayload): Promise<OnboardingResult> {
  const res = await api.post<OnboardingResult>('/onboarding', data);
  return res.data;
}

/** POST /api/tenant/:tenantId/settings — update active bot status and LLM overrides */
export async function updateTenantSettings(
  tenantId: string,
  data: DashboardControlPayload
): Promise<DashboardControlResult> {
  const res = await api.post<DashboardControlResult>(`/tenant/${tenantId}/settings`, data);
  return res.data;
}

/** GET /api/logs/:tenantId — fetch conversation logs */
export async function getLogs(tenantId: string): Promise<LogsResult> {
  const res = await api.get<LogsResult>(`/logs/${tenantId}`);
  return res.data;
}

/** GET /api/plan/:tenantId — fetch plan quota */
export async function getPlan(tenantId: string): Promise<PlanResult> {
  const res = await api.get<PlanResult>(`/plan/${tenantId}`);
  return res.data;
}

/** GET /api/health — liveness probe */
export async function getHealth(): Promise<HealthResult> {
  const res = await api.get<HealthResult>('/health');
  return res.data;
}

export default api;
