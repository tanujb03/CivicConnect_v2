// CivicConnect v2 — Shared Type Definitions
// Used by citizen-expo and field-worker-expo

export type CaseStatus =
  | 'submitted'
  | 'ai_processing'
  | 'triaged'
  | 'assigned'
  | 'in_progress'
  | 'evidence_uploaded'
  | 'verification_requested'
  | 'resolved'
  | 'reopened'
  | 'closed';

export type CasePriority = 'critical' | 'high' | 'medium' | 'low';

export type IssueCategory =
  | 'roads'
  | 'sanitation'
  | 'water'
  | 'lighting'
  | 'drainage'
  | 'parks'
  | 'public_transport'
  | 'encroachment'
  | 'noise'
  | 'other';

export type EvidenceType = 'image' | 'video' | 'audio' | 'text';

export type UserRole =
  | 'CITIZEN'
  | 'FIELD_WORKER'
  | 'DEPARTMENT_OPERATOR'
  | 'DEPARTMENT_MANAGER'
  | 'WARD_OFFICER'
  | 'CITY_ADMIN'
  | 'SUPER_ADMIN';

// ─── Auth ─────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  name: string;
  phone?: string;
  email?: string;
  role: UserRole;
  avatar_url?: string;
  language: string;
  ward?: string;
  locality?: string;
}

export interface OtpRequestPayload {
  phone?: string;
  email?: string;
}

export interface OtpVerifyPayload {
  phone?: string;
  email?: string;
  otp: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

// ─── Civic Case ───────────────────────────────────────────

export interface Location {
  lat: number;
  lng: number;
  accuracy?: number;
  address?: string;
  ward?: string;
  landmark?: string;
}

export interface EvidenceItem {
  id: string;
  type: EvidenceType;
  url: string;
  thumbnail_url?: string;
  mime_type: string;
  uploaded_at: string;
  uploader_id: string;
  source: 'CITIZEN' | 'FIELD_WORKER' | 'MUNICIPAL_INSPECTION';
  caption?: string;
}

export interface AIClassification {
  category: IssueCategory;
  subcategory?: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  summary: string;
  suggested_department: string;
  confidence: number;
  reasoning?: string[];
  model?: string;
  model_version?: string;
  processed_at: string;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  description: string;
  actor?: string;
  actor_role?: UserRole;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface CivicCase {
  id: string;
  case_number: string; // CC-XXXX
  title: string;
  description?: string;
  status: CaseStatus;
  priority: CasePriority;
  category: IssueCategory;
  subcategory?: string;
  location: Location;
  evidence: EvidenceItem[];
  ai_classification?: AIClassification;
  timeline: TimelineEvent[];
  supporter_count: number;
  reporter_count: number;
  created_at: string;
  updated_at: string;
  assigned_department?: string;
  work_order_id?: string;
  verification_deadline?: string;
  is_recurring?: boolean;
  related_case_ids?: string[];
  // citizen-specific fields
  my_role?: 'reporter' | 'supporter' | 'witness';
  requires_my_action?: boolean;
}

// ─── Duplicate / Fusion ───────────────────────────────────

export interface DuplicateCandidate {
  case_id: string;
  case_number: string;
  title: string;
  similarity_score: number;
  distance_meters: number;
  status: CaseStatus;
  supporter_count: number;
}

// ─── Report / Intake ──────────────────────────────────────

export interface ReportDraft {
  id: string; // local UUID
  text?: string;
  location?: Location;
  landmark?: string;
  images: string[]; // local file URIs
  audio_uri?: string;
  video_uri?: string;
  created_at: string;
  sync_status: 'draft' | 'queued' | 'uploading' | 'synced' | 'error';
  idempotency_key: string;
  error_message?: string;
}

export interface IntakeSubmitPayload {
  text?: string;
  location: Location;
  landmark?: string;
  image_refs?: string[]; // presigned upload refs
  audio_ref?: string;
  video_ref?: string;
  language?: string;
  idempotency_key: string;
}

export interface AIIntakeResult {
  intake_id: string;
  classification: AIClassification;
  duplicate_candidates: DuplicateCandidate[];
  transcript?: string;
  detected_language?: string;
}

// ─── Notifications ────────────────────────────────────────

export type NotificationEventType =
  | 'case_assigned'
  | 'case_in_progress'
  | 'evidence_uploaded'
  | 'verification_requested'
  | 'case_resolved'
  | 'case_reopened'
  | 'duplicate_found'
  | 'department_requested_info'
  | 'case_supported'
  | 'incident_nearby';

export interface AppNotification {
  id: string;
  type: NotificationEventType;
  title: string;
  body: string;
  case_id?: string;
  case_number?: string;
  read: boolean;
  requires_action?: boolean;
  created_at: string;
}

// ─── Work Order (Field Worker) ────────────────────────────

export type WorkOrderStatus =
  | 'assigned'
  | 'acknowledged'
  | 'en_route'
  | 'on_site'
  | 'in_progress'
  | 'evidence_uploaded'
  | 'completed';

export interface WorkOrder {
  id: string;
  case_id: string;
  case_number: string;
  title: string;
  description?: string;
  location: Location;
  priority: CasePriority;
  status: WorkOrderStatus;
  instructions?: string;
  required_evidence?: string[];
  assigned_to: string;
  assigned_at: string;
  deadline?: string;
  sla_hours?: number;
  original_evidence: EvidenceItem[];
  department: string;
  // field work fields
  start_time?: string;
  completion_time?: string;
  work_note?: string;
  resolution_evidence?: EvidenceItem[];
  materials_used?: string;
}

// ─── Community ────────────────────────────────────────────

export interface CommunityActivity {
  case_id: string;
  case_number: string;
  title: string;
  category: IssueCategory;
  status: CaseStatus;
  location: Location;
  supporter_count: number;
  last_activity_at: string;
  distance_meters?: number;
}

// ─── Profile ──────────────────────────────────────────────

export interface CitizenProfile {
  user_id?: string;
  name?: string;
  phone?: string;
  email?: string;
  language?: string;
  accessibility?: AccessibilityPrefs;
  notification_prefs?: NotificationPrefs;
  locality?: string;
  ward?: string;
  // civic activity
  cases_reported?: number;
  cases_supported?: number;
  evidence_contributions?: number;
  verification_contributions?: number;
  // nested structure support
  user?: AuthUser;
  activity?: {
    cases_reported?: number;
    cases_supported?: number;
    evidence_contributions?: number;
    verifications_completed?: number;
    verification_contributions?: number;
  };
  settings?: Record<string, unknown>;
}

export interface AccessibilityPrefs {
  large_text: boolean;
  high_contrast: boolean;
  reduced_motion: boolean;
  simplified_language: boolean;
  voice_playback: boolean;
}

export interface NotificationPrefs {
  case_updates: boolean;
  nearby_activity: boolean;
  community: boolean;
  incidents: boolean;
  push_enabled: boolean;
}

// ─── Map ──────────────────────────────────────────────────

export interface MapCaseMarker {
  id?: string;
  case_id: string;
  case_number: string;
  lat: number;
  lng: number;
  status: CaseStatus;
  category: IssueCategory;
  priority: CasePriority;
  title: string;
  supporter_count?: number;
}

export interface MapViewport {
  north: number;
  south: number;
  east: number;
  west: number;
}

// ─── API Response Shapes ──────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
