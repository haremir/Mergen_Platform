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
  sector: string;
  persona: string;
  meta_phone_id: string;
  meta_access_token?: string;
  product: string;
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

export interface TenantListEntry {
  tenant_id: string;
  business_name: string;
  sector: string;
  plan: string;
  whatsapp_phone_number_id: string | null;
  created_at: string;
  status: 'active' | 'pending_verification' | 'inactive';
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

/** GET /api/tenant — mocked list of all tenants (for Master Admin UI) */
export async function getTenants(): Promise<TenantListEntry[]> {
  // Simulate network latency for premium feel
  await new Promise((resolve) => setTimeout(resolve, 300));
  return [
    {
      tenant_id: '4cc9eef0-82eb-54ea-9999-desktest9999',
      business_name: 'Acme Barber Istanbul',
      sector: 'desk',
      plan: 'starter',
      whatsapp_phone_number_id: 'WABA_PHONE_ID_1001',
      created_at: '2026-07-10T12:00:00Z',
      status: 'active',
    },
    {
      tenant_id: '84a33b25-dc76-4743-b3cc-6bc500cb709f',
      business_name: 'Acme Hair Care & Salon',
      sector: 'desk',
      plan: 'business',
      whatsapp_phone_number_id: 'WABA_PHONE_ID_1002',
      created_at: '2026-07-12T15:30:00Z',
      status: 'active',
    },
    {
      tenant_id: 'a8f6955c-2a12-4cc1-9ce7-815d4bc5fc41',
      business_name: 'Luxe Kuaför Bebek',
      sector: 'desk',
      plan: 'premium',
      whatsapp_phone_number_id: null,
      created_at: '2026-07-11T09:15:00Z',
      status: 'pending_verification',
    },
    {
      tenant_id: '92f076d1-d912-4037-a69f-8db3ebdb8de3',
      business_name: 'Retro Barber Kadıköy',
      sector: 'desk',
      plan: 'free',
      whatsapp_phone_number_id: 'WABA_PHONE_ID_1004',
      created_at: '2026-07-09T18:45:00Z',
      status: 'inactive',
    }
  ];
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
