import axios from "axios";

let rawBase =
  (import.meta as any).env?.VITE_API_BASE_URL ??
  (import.meta as any).env?.VITE_API_BASE ??
  "http://localhost:8000/api";

if (!rawBase.endsWith("/api")) {
  rawBase = rawBase.replace(/\/+$/, "") + "/api";
}
const API_BASE = rawBase;

export const TOKEN_KEY = "katip_jwt_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

// Request Interceptor: JWT header
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: 401 handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken();
      if (!window.location.hash.includes("/login")) {
        window.location.hash = "#/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

export async function loginApi(email: string, password: string) {
  const response = await api.post("/auth/login", { email, password });
  if (response.data.access_token) {
    setToken(response.data.access_token);
  }
  return response.data;
}

export async function getProjectsApi() {
  const response = await api.get("/katip/projects");
  return response.data;
}

export async function createProjectApi(data: {
  brand_name: string;
  sector: string;
  tone_rules?: string[];
  forbidden_words?: string[];
  cms_config?: any;
}) {
  const response = await api.post("/katip/projects", data);
  return response.data;
}

export async function updateProjectApi(
  projectId: string,
  data: {
    brand_name: string;
    sector: string;
    tone_rules?: string[];
    forbidden_words?: string[];
    cms_config?: any;
  }
) {
  const response = await api.put(`/katip/projects/${projectId}`, data);
  return response.data;
}

export async function getProjectMetricsApi(projectId: string) {
  const response = await api.get(`/katip/projects/${projectId}/metrics`);
  return response.data;
}

export async function getTopicsApi(params?: {
  brand_guide_id?: string;
  topic_status?: string;
  limit?: number;
  offset?: number;
}) {
  const response = await api.get("/katip/topics", { params });
  return response.data;
}

export async function createTopicApi(data: {
  topic_title: string;
  brand_guide_id?: string;
  target_keywords?: string[];
  priority?: number;
}) {
  const response = await api.post("/katip/topics", data);
  return response.data;
}

export async function getDraftsApi(params?: {
  brand_guide_id?: string;
  draft_status?: string;
  limit?: number;
  offset?: number;
}) {
  const response = await api.get("/katip/drafts", { params });
  return response.data;
}

export async function getDraftDetailApi(draftId: string) {
  const response = await api.get(`/katip/drafts/${draftId}`);
  return response.data;
}

export async function submitFeedbackApi(draftId: string, note: string, authorLabel?: string) {
  const response = await api.post(`/katip/drafts/${draftId}/feedback`, {
    note,
    author_label: authorLabel,
  });
  return response.data;
}

export async function updateDraftStatusApi(draftId: string, status: string) {
  const response = await api.put(`/katip/drafts/${draftId}/status`, { status });
  return response.data;
}

export async function getDashboardSummaryApi(brandGuideId?: string) {
  const response = await api.get("/katip/dashboard/summary", {
    params: brandGuideId ? { brand_guide_id: brandGuideId } : undefined,
  });
  return response.data;
}

