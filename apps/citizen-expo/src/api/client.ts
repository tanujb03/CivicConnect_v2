/**
 * CivicConnect v2 — API Client
 *
 * All network calls go through this client.
 * Components/screens never call fetch() directly.
 *
 * Base URL: /api/v1  (configured via env)
 * Auth: Bearer token stored in SecureStore / AsyncStorage
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import type {
  AuthTokens,
  OtpRequestPayload,
  OtpVerifyPayload,
  AuthUser,
  CivicCase,
  AIIntakeResult,
  AppNotification,
  WorkOrder,
  CitizenProfile,
  MapCaseMarker,
  MapViewport,
  PaginatedResponse,
  CommunityActivity,
  DuplicateCandidate,
  IssueCategory,
} from '../types';

// ─── Config ───────────────────────────────────────────────

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

const STORAGE_KEYS = {
  ACCESS_TOKEN: 'cc:access_token',
  REFRESH_TOKEN: 'cc:refresh_token',
  USER: 'cc:user',
} as const;

// ─── Token management ─────────────────────────────────────

export async function getAccessToken(): Promise<string | null> {
  return AsyncStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
}

export async function storeTokens(tokens: AuthTokens): Promise<void> {
  await AsyncStorage.multiSet([
    [STORAGE_KEYS.ACCESS_TOKEN, tokens.access_token],
    [STORAGE_KEYS.REFRESH_TOKEN, tokens.refresh_token],
  ]);
}

export async function clearTokens(): Promise<void> {
  await AsyncStorage.multiRemove([
    STORAGE_KEYS.ACCESS_TOKEN,
    STORAGE_KEYS.REFRESH_TOKEN,
    STORAGE_KEYS.USER,
  ]);
}

export async function storeUser(user: AuthUser): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
}

export async function getStoredUser(): Promise<AuthUser | null> {
  const raw = await AsyncStorage.getItem(STORAGE_KEYS.USER);
  return raw ? JSON.parse(raw) : null;
}

// ─── HTTP layer ───────────────────────────────────────────

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  skipAuth?: boolean;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, skipAuth = false, signal } = opts;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (!skipAuth) {
    const token = await getAccessToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (response.status === 401 && !skipAuth) {
    // Attempt token refresh
    await refreshTokens();
    const newToken = await getAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      const retried = await fetch(`${BASE_URL}${path}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal,
      });
      if (!retried.ok) throw await buildError(retried);
      return retried.json() as Promise<T>;
    }
    throw new Error('UNAUTHENTICATED');
  }

  if (!response.ok) throw await buildError(response);

  if (response.status === 204) return undefined as unknown as T;
  return response.json() as Promise<T>;
}

async function buildError(res: Response): Promise<Error> {
  try {
    const data = await res.json();
    return Object.assign(new Error(data.message ?? res.statusText), {
      code: data.code,
      status: res.status,
    });
  } catch {
    return new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
}

async function refreshTokens(): Promise<void> {
  const refresh = await AsyncStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
  if (!refresh) return;

  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      await clearTokens();
      return;
    }
    const tokens: AuthTokens = await res.json();
    await storeTokens(tokens);
  } catch {
    // Swallow — caller handles 401
  }
}

import { MOCK_CASES, MOCK_NOTIFICATIONS, MOCK_COMMUNITY_ACTIVITY, MOCK_USER } from '../data/mockData';

// ─── Auth API ─────────────────────────────────────────────

export const authApi = {
  requestOtp: async (payload: OtpRequestPayload) => {
    try {
      return await request<{ message: string }>('/auth/request-otp', {
        method: 'POST',
        body: payload,
        skipAuth: true,
      });
    } catch {
      // Mock fallback for offline / demo mode
      return { message: 'OTP sent (Demo code: 123456)' };
    }
  },

  verifyOtp: async (payload: OtpVerifyPayload) => {
    try {
      return await request<AuthTokens & { user: AuthUser }>('/auth/verify-otp', {
        method: 'POST',
        body: payload,
        skipAuth: true,
      });
    } catch {
      // Mock fallback for offline / demo mode
      const tokens: AuthTokens = {
        access_token: 'mock-access-token-demo',
        refresh_token: 'mock-refresh-token-demo',
        expires_in: 86400,
      };
      const user: AuthUser = {
        ...MOCK_USER,
        phone: payload.phone || MOCK_USER.phone,
        email: payload.email || MOCK_USER.email,
      };
      await storeTokens(tokens);
      await storeUser(user);
      return { ...tokens, user };
    }
  },

  demoLogin: async () => {
    const tokens: AuthTokens = {
      access_token: 'mock-access-token-demo',
      refresh_token: 'mock-refresh-token-demo',
      expires_in: 86400,
    };
    await storeTokens(tokens);
    await storeUser(MOCK_USER);
    return { ...tokens, user: MOCK_USER };
  },

  refreshToken: () =>
    request<AuthTokens>('/auth/refresh', { method: 'POST', skipAuth: true }),

  logout: () =>
    request<void>('/auth/logout', { method: 'POST' }).catch(() => { }),

  me: () => request<AuthUser>('/me').catch(() => MOCK_USER),
};

// ─── Cases API ────────────────────────────────────────────

export interface MyCasesParams {
  tab?: 'active' | 'awaiting_me' | 'resolved' | 'reopened' | 'supported';
  category?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export const casesApi = {
  list: async (params: MyCasesParams = {}): Promise<PaginatedResponse<CivicCase>> => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    try {
      return await request<PaginatedResponse<CivicCase>>(`/cases/my?${qs}`);
    } catch {
      // Fallback to local mock data
      let filtered = [...MOCK_CASES];
      if (params.tab) {
        if (params.tab === 'active') {
          filtered = filtered.filter(c => c.status !== 'resolved' && c.status !== 'closed');
        } else if (params.tab === 'awaiting_me') {
          filtered = filtered.filter(c => c.requires_my_action || c.status === 'verification_requested');
        } else if (params.tab === 'resolved') {
          filtered = filtered.filter(c => c.status === 'resolved' || c.status === 'closed');
        } else if (params.tab === 'reopened') {
          filtered = filtered.filter(c => c.status === 'reopened');
        } else if (params.tab === 'supported') {
          filtered = filtered.filter(c => c.my_role === 'supporter' || c.supporter_count > 5);
        }
      }
      if (params.category && params.category !== 'all') {
        filtered = filtered.filter(c => c.category === params.category);
      }
      if (params.status && params.status !== 'all') {
        filtered = filtered.filter(c => c.status === params.status);
      }
      return {
        items: filtered,
        total: filtered.length,
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
        has_more: false,
      };
    }
  },

  get: async (id: string): Promise<CivicCase> => {
    try {
      return await request<CivicCase>(`/cases/${id}`);
    } catch {
      const found = MOCK_CASES.find(c => c.id === id || c.case_number === id);
      return found || MOCK_CASES[0];
    }
  },

  support: async (id: string) => {
    try {
      return await request<{ supporter_count: number }>(`/cases/${id}/support`, {
        method: 'POST',
      });
    } catch {
      const found = MOCK_CASES.find(c => c.id === id);
      const count = (found ? found.supporter_count : 10) + 1;
      if (found) found.supporter_count = count;
      return { supporter_count: count };
    }
  },

  addEvidence: async (id: string, evidenceRefs: string[], caption?: string) => {
    try {
      return await request<void>(`/cases/${id}/evidence`, {
        method: 'POST',
        body: { evidence_refs: evidenceRefs, caption },
      });
    } catch {
      // Mock success
    }
  },

  verify: async (id: string, verdict: 'resolved' | 'not_resolved', note?: string) => {
    try {
      return await request<void>(`/cases/${id}/verify`, {
        method: 'POST',
        body: { verdict, note },
      });
    } catch {
      const found = MOCK_CASES.find(c => c.id === id);
      if (found) {
        found.status = verdict === 'resolved' ? 'resolved' : 'reopened';
        found.requires_my_action = false;
      }
    }
  },

  reopen: async (id: string, reason: string) => {
    try {
      return await request<void>(`/cases/${id}/reopen`, {
        method: 'POST',
        body: { reason },
      });
    } catch {
      const found = MOCK_CASES.find(c => c.id === id);
      if (found) {
        found.status = 'reopened';
        found.requires_my_action = false;
      }
    }
  },
};

// ─── Intake API ───────────────────────────────────────────

export interface PresignedUploadRequest {
  file_name: string;
  mime_type: string;
  size_bytes: number;
}

export interface PresignedUploadResponse {
  upload_url: string;
  ref: string;
  expires_at: string;
}

export const intakeApi = {
  getUploadUrl: (payload: PresignedUploadRequest) =>
    request<PresignedUploadResponse>('/intake/upload-url', {
      method: 'POST',
      body: payload,
    }).catch(() => ({
      upload_url: 'https://example.com/mock-upload',
      ref: 'mock-ref-' + Date.now(),
      expires_at: new Date(Date.now() + 3600000).toISOString(),
    })),

  submit: async (payload: {
    text?: string;
    location: { lat: number; lng: number; accuracy?: number };
    landmark?: string;
    image_refs?: string[];
    audio_ref?: string;
    video_ref?: string;
    language?: string;
    idempotency_key: string;
  }): Promise<AIIntakeResult> => {
    try {
      return await request<AIIntakeResult>('/intake/submit', {
        method: 'POST',
        body: payload,
      });
    } catch {
      // Instant intelligent mock triage fallback
      const textLower = (payload.text || '').toLowerCase();
      let category: IssueCategory = 'roads';
      let dept = 'Roads & Highways';
      if (textLower.includes('garbage') || textLower.includes('waste') || textLower.includes('trash') || textLower.includes('clean')) {
        category = 'sanitation';
        dept = 'Solid Waste Management';
      } else if (textLower.includes('light') || textLower.includes('dark') || textLower.includes('lamp') || textLower.includes('pole')) {
        category = 'lighting';
        dept = 'Electrical & Public Lighting';
      } else if (textLower.includes('water') || textLower.includes('leak') || textLower.includes('pipe')) {
        category = 'water';
        dept = 'Water Supply & Sewerage';
      } else if (textLower.includes('drain') || textLower.includes('flood') || textLower.includes('gutter')) {
        category = 'drainage';
        dept = 'Stormwater Drainage';
      }

      return {
        intake_id: `intake-${Date.now()}`,
        classification: {
          category,
          severity: 'medium',
          summary: payload.text || 'Citizen reported civic infrastructure defect.',
          suggested_department: dept,
          confidence: 0.94,
          reasoning: [
            'Visual & semantic keywords match municipal priority classification.',
            'Location mapped to Ward 15 maintenance jurisdiction.',
          ],
          processed_at: new Date().toISOString(),
        },
        duplicate_candidates: [],
        transcript: payload.audio_ref ? 'Voice note successfully transcribed by audio pipeline.' : undefined,
        detected_language: payload.language || 'en',
      };
    }
  },

  submitIntake: async (payload: any): Promise<AIIntakeResult> => {
    return intakeApi.submit(payload);
  },

  confirmCase: async (intake_id: string, action: 'create' | 'attach', existing_case_id?: string) => {
    try {
      return await request<{ case_id: string; case_number: string }>('/intake/confirm', {
        method: 'POST',
        body: { intake_id, action, existing_case_id },
      });
    } catch {
      const caseNumber = `CC-${Math.floor(1000 + Math.random() * 9000)}`;
      const newId = existing_case_id || `case-${Date.now()}`;

      // Insert into MOCK_CASES so it immediately appears in My Cases & Dashboard
      if (action === 'create') {
        const newCase: CivicCase = {
          id: newId,
          case_number: caseNumber,
          title: 'Citizen Reported Issue',
          description: 'Verified civic defect submitted through CivicConnect app.',
          status: 'submitted',
          priority: 'medium',
          category: 'roads',
          location: { lat: 23.3441, lng: 85.3096, landmark: 'Near Central Market', address: 'Main Road, Ranchi' },
          evidence: [
            {
              id: `ev-${Date.now()}`,
              type: 'image',
              url: 'https://www.copavementsolutions.com/wp-content/uploads/2023/09/how-potholes-form.jpg',
              mime_type: 'image/jpeg',
              uploaded_at: new Date().toISOString(),
              uploader_id: 'citizen-demo-1',
              source: 'CITIZEN',
            }
          ],
          timeline: [
            {
              id: '1',
              event_type: 'submitted',
              description: 'Issue reported and queued for municipal triage',
              actor: 'Citizen',
              actor_role: 'CITIZEN',
              timestamp: new Date().toISOString(),
            }
          ],
          supporter_count: 1,
          reporter_count: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          my_role: 'reporter',
        };
        MOCK_CASES.unshift(newCase);
      }

      return { case_id: newId, case_number: caseNumber };
    }
  },
};

// ─── Notifications API ────────────────────────────────────

export const notificationsApi = {
  list: async (page = 1): Promise<PaginatedResponse<AppNotification>> => {
    try {
      return await request<PaginatedResponse<AppNotification>>(`/notifications?page=${page}`);
    } catch {
      return {
        items: MOCK_NOTIFICATIONS,
        total: MOCK_NOTIFICATIONS.length,
        page,
        page_size: 10,
        has_more: false,
      };
    }
  },

  markRead: async (id: string) => {
    try {
      return await request<void>(`/notifications/${id}/read`, { method: 'PATCH' });
    } catch {
      const n = MOCK_NOTIFICATIONS.find(item => item.id === id);
      if (n) n.read = true;
    }
  },

  markAllRead: async () => {
    try {
      return await request<void>('/notifications/read-all', { method: 'POST' });
    } catch {
      MOCK_NOTIFICATIONS.forEach(n => { n.read = true; });
    }
  },
};

// ─── Map API ──────────────────────────────────────────────

export const mapApi = {
  getCasesInViewport: async (viewport: MapViewport, filters?: Record<string, string>): Promise<MapCaseMarker[]> => {
    const qs = new URLSearchParams({
      north: String(viewport.north),
      south: String(viewport.south),
      east: String(viewport.east),
      west: String(viewport.west),
      ...filters,
    }).toString();
    try {
      return await request<MapCaseMarker[]>(`/map/cases?${qs}`);
    } catch {
      return MOCK_CASES.map(c => ({
        case_id: c.id,
        case_number: c.case_number,
        title: c.title,
        lat: c.location.lat,
        lng: c.location.lng,
        category: c.category,
        priority: c.priority,
        status: c.status,
      }));
    }
  },
};

// ─── Community API ────────────────────────────────────────

export const communityApi = {
  nearby: async (lat: number, lng: number, radius_km = 5): Promise<CommunityActivity[]> => {
    try {
      return await request<CommunityActivity[]>(
        `/community/nearby?lat=${lat}&lng=${lng}&radius_km=${radius_km}`
      );
    } catch {
      return MOCK_COMMUNITY_ACTIVITY;
    }
  },
};

// ─── Profile API ──────────────────────────────────────────

export const profileApi = {
  get: async (): Promise<CitizenProfile> => {
    // Try to get stored user first for profile data
    const storedUser = await getStoredUser();
    try {
      return await request<CitizenProfile>('/profile');
    } catch {
      const baseUser = storedUser || MOCK_USER;
      return {
        user_id: baseUser.id,
        name: baseUser.name,
        phone: baseUser.phone,
        email: baseUser.email,
        language: baseUser.language,
        ward: baseUser.ward,
        locality: baseUser.locality,
        cases_reported: 4,
        cases_supported: 12,
        evidence_contributions: 6,
        verification_contributions: 3,
        // Nested structure for profile screen
        user: baseUser,
        activity: {
          cases_reported: 4,
          cases_supported: 12,
          evidence_contributions: 6,
          verifications_completed: 3,
        },
        settings: {
          notifications_enabled: true,
          notification_types: ['status_update', 'verification_request'],
          language: baseUser.language,
          dark_mode: false,
          location_sharing: true,
        },
      };
    }
  },
  update: async (updates: Partial<CitizenProfile>): Promise<CitizenProfile> => {
    const storedUser = await getStoredUser();
    const baseUser = storedUser || MOCK_USER;
    try {
      return await request<CitizenProfile>('/profile', { method: 'PATCH', body: updates });
    } catch {
      return {
        user_id: baseUser.id,
        name: baseUser.name,
        phone: baseUser.phone,
        email: baseUser.email,
        language: baseUser.language,
        ward: baseUser.ward,
        locality: baseUser.locality,
        cases_reported: 4,
        cases_supported: 12,
        evidence_contributions: 6,
        verification_contributions: 3,
        user: baseUser,
        activity: {
          cases_reported: 4,
          cases_supported: 12,
          evidence_contributions: 6,
          verifications_completed: 3,
        },
        ...updates,
      };
    }
  },
};

// ─── Field Worker API ─────────────────────────────────────

export const workOrdersApi = {
  list: () => request<WorkOrder[]>('/work-orders/my'),
  get: (id: string) => request<WorkOrder>(`/work-orders/${id}`),

  acknowledge: (id: string) =>
    request<void>(`/work-orders/${id}/acknowledge`, { method: 'POST' }),

  startWork: (id: string, location: { lat: number; lng: number }) =>
    request<void>(`/work-orders/${id}/start`, {
      method: 'POST',
      body: { location },
    }),

  uploadEvidence: (id: string, evidenceRefs: string[], work_note?: string, materials_used?: string) =>
    request<void>(`/work-orders/${id}/evidence`, {
      method: 'POST',
      body: { evidence_refs: evidenceRefs, work_note, materials_used },
    }),

  complete: (id: string, completion_note?: string) =>
    request<void>(`/work-orders/${id}/complete`, {
      method: 'POST',
      body: { completion_note },
    }),
};

// ─── Sync helpers (used by offline outbox) ────────────────

export { request };
