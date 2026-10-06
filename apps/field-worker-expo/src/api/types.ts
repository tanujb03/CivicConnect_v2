// API domain types — shared by real endpoints and mock data layer
// IMPORTANT: This file must NOT import any expo-* or react-native packages

export type Priority = 'P1' | 'P2' | 'P3';
export type WorkOrderStatus = 'OPEN' | 'IN_PROGRESS' | 'DONE' | 'CANCELLED';
export type Category = 'ROAD' | 'WATER' | 'SEWER' | 'ELECTRICAL' | 'PARKS' | 'DEBRIS' | 'OTHER';

export interface WorkOrder {
  id: string;
  caseId: string;      // links to citizen case
  title: string;
  category: Category;
  priority: Priority;
  status: WorkOrderStatus;
  slaHours: number;    // total SLA window in hours
  slaDeadline: string; // ISO 8601
  assignedTo: string;  // worker employee ID
  ward: string;
  address: string;
  lat?: number;
  lng?: number;
  description: string;
  citizenName?: string;
  citizenPhone?: string;
  createdAt: string;   // ISO 8601
  updatedAt: string;   // ISO 8601
  closedAt?: string;   // ISO 8601
}

export interface WorkOrderUpdate {
  status?: WorkOrderStatus;
  note?: string;
  photos?: string[];   // file URIs (uploaded) or attachment IDs
}

export interface WorkerProfile {
  id: string;
  name: string;
  employeeId: string;
  ward: string;
  department: string;
  phone: string;
  email: string;
  photoUrl?: string;
}

export interface KpiSummary {
  openCount: number;
  doneToday: number;
  overdueCount: number;
  slaBreachRate: number; // 0–1
  avgCloseHours: number;
}

export interface ApiResponse<T> {
  data: T;
  meta?: {
    page: number;
    pageSize: number;
    total: number;
  };
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
