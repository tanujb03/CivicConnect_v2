/**
 * CivicConnect v2 — API Client Boundary
 * Section 51A — API Contract Specification
 *
 * All admin data access must go through this layer.
 * Do NOT call fetch/axios directly from components.
 * All endpoints follow /api/v1 base path.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

// ─── Auth helpers ────────────────────────────────────────────────────────────

function getToken(): string | null {
  return localStorage.getItem('civic_access_token');
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem('civic_access_token', access);
  localStorage.setItem('civic_refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('civic_access_token');
  localStorage.removeItem('civic_refresh_token');
}

// ─── Generic fetch wrapper ────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let errBody: { error?: { code?: string; message?: string } } = {};
    try { errBody = await res.json(); } catch { /* ignore */ }
    const msg = errBody?.error?.message ?? `HTTP ${res.status}`;
    const err = new Error(msg) as Error & { code?: string; status: number };
    err.code = errBody?.error?.code;
    err.status = res.status;
    throw err;
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function mutation<T>(
  path: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  body?: unknown
): Promise<T> {
  const idempotencyKey = crypto.randomUUID();
  return request<T>(path, {
    method,
    headers: { 'Idempotency-Key': idempotencyKey },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

// ─── 51A.2 Auth ───────────────────────────────────────────────────────────────

export interface AuthSession {
  user: { id: string; name: string; role: string };
  access_token: string;
  refresh_token: string;
}

export const authApi = {
  login: (identifier: string, password: string) =>
    mutation<AuthSession>('/auth/login', 'POST', { identifier, password }),

  refresh: (refresh_token: string) =>
    mutation<{ access_token: string; refresh_token: string }>(
      '/auth/refresh',
      'POST',
      { refresh_token }
    ),

  me: () => request<AuthSession['user']>('/auth/me'),
};

// ─── 51A.4 Cases ─────────────────────────────────────────────────────────────

export interface CaseLocation {
  latitude: number;
  longitude: number;
  accuracy_m?: number;
}

export interface CivicCase {
  id: string;
  case_number: string;
  title: string | null;
  description: string | null;
  status: string;
  category: string | null;
  subcategory?: string | null;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null;
  priority: 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL';
  location: CaseLocation;
  ward_id?: string | null;
  department_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export interface CasesQuery {
  status?: string;
  category?: string;
  priority?: string;
  ward_id?: string;
  department_id?: string;
  sort?: string;
  from?: string;
  until?: string;
  cursor?: string;
  limit?: number;
}

export const casesApi = {
  list: (params: CasesQuery = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== '')
          .map(([k, v]) => [k, String(v)])
      )
    ).toString();
    return request<PaginatedResponse<CivicCase>>(`/cases${qs ? `?${qs}` : ''}`);
  },

  get: (caseId: string) => request<CivicCase>(`/cases/${caseId}`),

  patch: (caseId: string, body: Partial<CivicCase>) =>
    mutation<CivicCase>(`/cases/${caseId}`, 'PATCH', body),

  createWorkOrder: (
    caseId: string,
    body: { assignee_id: string; instructions: string; due_at: string }
  ) => mutation<{ id: string }>(`/cases/${caseId}/work-orders`, 'POST', body),

  timeline: (caseId: string) =>
    request<PaginatedResponse<{ id: string; event_type: string; actor_id: string; timestamp: string; metadata: object }>>(
      `/cases/${caseId}/timeline`
    ),

  fusionAnalyze: (caseId: string) =>
    mutation<{
      matches: { case_id: string; similarity: number; signals: object }[];
      recommendation: string;
    }>(`/cases/${caseId}/fusion/analyze`, 'POST'),
};

// ─── 51A.8 AI Triage ─────────────────────────────────────────────────────────

export interface TriageRecommendation {
  severity: string;
  priority: string;
  department: string;
  sla_hours: number;
}

export interface TriageAnalysis {
  recommendation: TriageRecommendation;
  confidence: number;
  reasons: string[];
  warnings: string[];
}

export const triageApi = {
  analyze: (caseId: string) =>
    mutation<TriageAnalysis>(`/cases/${caseId}/triage/analyze`, 'POST'),

  decide: (
    caseId: string,
    body: {
      severity: string;
      priority: string;
      department_id: string;
      sla_hours: number;
      reason: string;
    }
  ) => mutation<void>(`/cases/${caseId}/triage/decision`, 'POST', body),
};

// ─── 51A.13 Analytics ────────────────────────────────────────────────────────

export interface AnalyticsOverview {
  open_cases: number;
  critical_cases: number;
  sla_at_risk: number;
  unassigned: number;
  awaiting_verification: number;
  reopened: number;
  median_resolution_hours: number;
  category_distribution: { category: string; count: number }[];
  daily_trend: { date: string; created: number; resolved: number }[];
}

export const analyticsApi = {
  overview: () => request<AnalyticsOverview>('/analytics/overview'),

  department: (departmentId: string) =>
    request<{
      incoming: number;
      active: number;
      resolved: number;
      median_resolution_hours: number;
      sla_compliance_pct: number;
      reopened: number;
      backlog_age_days: number;
    }>(`/analytics/departments/${departmentId}`),

  incidents: () =>
    request<PaginatedResponse<{ id: string; title: string; status: string; created_at: string }>>(
      '/analytics/incidents'
    ),
};

// ─── 51A.12 Map / Geospatial ──────────────────────────────────────────────────

export interface MapCase {
  id: string;
  case_number: string;
  location: CaseLocation;
  status: string;
  category: string | null;
  priority: string;
}

export interface MapQuery {
  bbox?: string;
  category?: string;
  status?: string;
  priority?: string;
  from?: string;
  until?: string;
  limit?: number;
}

export const mapApi = {
  cases: (params: MapQuery = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      )
    ).toString();
    return request<{ items: MapCase[] }>(`/map/cases${qs ? `?${qs}` : ''}`);
  },

  hotspots: () =>
    request<{ items: { id: string; geometry: object; metrics: object }[] }>('/map/hotspots'),

  recurringProblems: () =>
    request<{ items: { id: string; category: string; recurrence_count: number; location: object }[] }>(
      '/map/recurring-problems'
    ),
};

// ─── 51A.14 Incidents ─────────────────────────────────────────────────────────

export const incidentsApi = {
  create: (body: {
    title: string;
    description: string;
    category: string;
    boundary: object;
    case_ids: string[];
  }) => mutation<{ id: string }>('/incidents', 'POST', body),

  get: (incidentId: string) =>
    request<{
      id: string;
      title: string;
      status: string;
      boundary: object;
      case_ids: string[];
      timeline: object[];
    }>(`/incidents/${incidentId}`),

  addCase: (incidentId: string, caseId: string) =>
    mutation<void>(`/incidents/${incidentId}/cases`, 'POST', { case_id: caseId }),
};

// ─── 51A.15 Copilot ───────────────────────────────────────────────────────────

export const copilotApi = {
  query: (
    query: string,
    scope: { ward_id?: string; department_id?: string; from?: string; until?: string } = {}
  ) =>
    mutation<{
      answer: string;
      data: object[];
      citations: { type: string; id: string }[];
      warnings: string[];
    }>('/copilot/query', 'POST', { query, scope }),
};
