import axios from 'axios';

/* ─────────────────────────────────────────────────────────────
   Axios instance — points to the FastAPI backend (Cloud & Local)
   ───────────────────────────────────────────────────────────── */
function sanitizeApiBaseUrl(raw: string): string {
  let url = (raw || "").trim();
  // Strip markdown, bracket or quotes artifacts like [https://...] or "https://..."
  url = url.replace(/^[\[\("']+|[\]\)"']+$/g, "").trim();
  // Fix single slash after protocol e.g. https:/domain -> https://domain
  url = url.replace(/^(https?):\/([^\/])/, "$1://$2");
  // Prepend https:// if protocol is missing (unless localhost)
  if (!/^https?:\/\//i.test(url)) {
    url = "https://" + url;
  }
  // Ensure it ends with /api
  url = url.replace(/\/+$/, "");
  if (!url.endsWith("/api")) {
    url = url + "/api";
  }
  return url;
}

const rawBase =
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (import.meta as any).env?.VITE_API_BASE ||
  'http://localhost:8000/api';

const api = axios.create({
  baseURL: sanitizeApiBaseUrl(rawBase),
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
  instagram_token?: string;
  telegram_token?: string;
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
  product: string;
  enabled_products?: string[];
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

export interface PlatformSettingsPayload {
  maintenance_mode: boolean;
  allow_new_registrations: boolean;
  global_system_alerts: string;
}

export interface PlatformAnalyticsResult {
  revenue: number;
  expenses: number;
  message_volume: number;
  active_tenants: number;
  status: string;
  metrics: {
    total_revenue: number;
    api_costs: number;
    active_tenants: number;
    total_messages: number;
  };
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
      tenant_id: 'pilot-dental-clinic-01',
      business_name: 'DentSmile Klinik & İçerik Ajansı',
      sector: 'dental_clinic',
      product: 'katip',
      plan: 'business',
      whatsapp_phone_number_id: null,
      created_at: '2026-07-20T10:00:00Z',
      status: 'active',
    },
    {
      tenant_id: 'elite-realestate-agency',
      business_name: 'Elite İnşaat & Gayrimenkul Ajansı',
      sector: 'real_estate',
      product: 'katip',
      plan: 'premium',
      whatsapp_phone_number_id: null,
      created_at: '2026-07-21T14:20:00Z',
      status: 'active',
    },
    {
      tenant_id: '4cc9eef0-82eb-54ea-9999-desktest9999',
      business_name: 'Acme Barber Istanbul',
      sector: 'hairdresser',
      product: 'desk',
      plan: 'starter',
      whatsapp_phone_number_id: 'WABA_PHONE_ID_1001',
      created_at: '2026-07-10T12:00:00Z',
      status: 'active',
    },
    {
      tenant_id: '84a33b25-dc76-4743-b3cc-6bc500cb709f',
      business_name: 'Acme Hair Care & Salon',
      sector: 'beauty_salon',
      product: 'desk',
      plan: 'business',
      whatsapp_phone_number_id: 'WABA_PHONE_ID_1002',
      created_at: '2026-07-12T15:30:00Z',
      status: 'active',
    },
    {
      tenant_id: 'a8f6955c-2a12-4cc1-9ce7-815d4bc5fc41',
      business_name: 'Luxe Kuaför Bebek',
      sector: 'hairdresser',
      product: 'desk',
      plan: 'premium',
      whatsapp_phone_number_id: null,
      created_at: '2026-07-11T09:15:00Z',
      status: 'pending_verification',
    },
    {
      tenant_id: '92f076d1-d912-4037-a69f-8db3ebdb8de3',
      business_name: 'Retro Barber Kadıköy',
      sector: 'restaurant',
      product: 'desk',
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

/** GET /api/platform/settings — fetch global platform settings */
export async function getPlatformSettings(): Promise<PlatformSettingsPayload> {
  const res = await api.get<PlatformSettingsPayload>('/platform/settings');
  return res.data;
}

/** POST /api/platform/settings — update global platform settings */
export async function updatePlatformSettings(data: PlatformSettingsPayload): Promise<{ status: string; message: string }> {
  const res = await api.post<{ status: string; message: string }>('/platform/settings', data);
  return res.data;
}

/** GET /api/platform/analytics — fetch global platform analytics */
export async function getPlatformAnalytics(): Promise<PlatformAnalyticsResult> {
  const res = await api.get<PlatformAnalyticsResult>('/platform/analytics');
  return res.data;
}

/* ─────────────────────────────────────────────────────────────
   Kâtip Product API Functions
   ───────────────────────────────────────────────────────────── */
export interface KatipTopicSummary {
  id: string;
  tenant_id: string;
  topic_title: string;
  target_keywords: string[] | null;
  status: string;
  priority: number;
  created_at: string;
}

export interface KatipTopicsResponse {
  tenant_id: string;
  total: number;
  items: KatipTopicSummary[];
}

export interface KatipDraftSummary {
  draft_id: string;
  topic_id: string;
  tenant_id: string;
  status: string;
  latest_version_number: number | null;
  created_at: string;
  updated_at: string;
}

export interface KatipDraftsResponse {
  tenant_id: string;
  total: number;
  items: KatipDraftSummary[];
}

export const ADMIN_TOKEN_KEY = "mergen_admin_jwt_token";

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function removeAdminToken(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}

api.interceptors.request.use(
  (config) => {
    const token = getAdminToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== '/login') {
      removeAdminToken();
    }
    return Promise.reject(error);
  }
);

export async function loginAdminApi(email: string, password: string) {
  const res = await api.post('/auth/login', { email, password });
  if (res.data.access_token) {
    setAdminToken(res.data.access_token);
  }
  return res.data;
}

export async function adminSetTenantPassword(tenantId: string, email: string, password: string) {
  const res = await api.post(`/admin/tenants/${tenantId}/set-password`, { email, password });
  return res.data;
}

export async function adminGetTenants() {
  const res = await api.get('/admin/tenants');
  return res.data;
}

export async function adminGetTenant(tenantId: string) {
  const res = await api.get(`/admin/tenants/${tenantId}`);
  return res.data;
}

export async function adminGetTenantDrafts(tenantId: string, status?: string) {
  const res = await api.get(`/admin/tenants/${tenantId}/drafts`, {
    params: status ? { status } : {},
  });
  return res.data;
}

export async function adminGetTenantDraft(tenantId: string, draftId: string) {
  const res = await api.get(`/admin/tenants/${tenantId}/drafts/${draftId}`);
  return res.data;
}

export default api;
