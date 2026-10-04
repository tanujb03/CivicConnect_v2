/**
 * CivicConnect Field Worker — API Client
 *
 * Implements F01–F05 contracts aligned with Section 51A.
 * All backend calls are routed through this layer with offline-safe fallbacks.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import type { WorkOrder } from '../types';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

// Sample mock data for robust offline and demo execution
const MOCK_WORK_ORDERS: WorkOrder[] = [
  {
    id: 'wo-101',
    case_id: 'case-501',
    case_number: 'CC-4012',
    title: 'Severe water main leak flooding pedestrian pathway',
    description: 'Fresh water main fractured near 17th Cross junction. Water pooling onto sidewalk and building foundations.',
    location: {
      lat: 12.9341,
      lng: 77.6219,
      address: '17th Cross, Sector 4, HSR Layout, Bengaluru',
      ward: 'Ward 174',
      landmark: 'Opposite BDA Complex Gate 2',
    },
    priority: 'critical',
    status: 'assigned',
    instructions: 'Isolate main valve V-14 immediately. Excavate 1.5m trench to inspect coupling. Replace damaged 4-inch PVC joint.',
    required_evidence: ['Excavation inspection photo', 'Replaced pipe joint photo', 'Restored surface photo'],
    assigned_to: 'worker-77',
    assigned_at: '2026-10-03T08:30:00Z',
    deadline: '2026-10-03T16:00:00Z',
    sla_hours: 8,
    department: 'Water Supply & Sewerage (BWSSB)',
    original_evidence: [
      {
        id: 'ev-1',
        type: 'image',
        url: 'https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?auto=format&fit=crop&w=800&q=80',
        mime_type: 'image/jpeg',
        uploaded_at: '2026-10-03T08:15:00Z',
        uploader_id: 'citizen-99',
        source: 'CITIZEN',
        caption: 'Gushing water near footpath curb',
      },
    ],
  },
  {
    id: 'wo-102',
    case_id: 'case-502',
    case_number: 'CC-4018',
    title: 'Dangerous unpaved asphalt crater after utility trenching',
    description: 'Open trench 3 meters long left uncompacted after telecom cabling. Two motorbikes slipped in morning rain.',
    location: {
      lat: 12.9388,
      lng: 77.6277,
      address: '27th Main Road, Sector 1, HSR Layout',
      ward: 'Ward 174',
      landmark: 'Near Shell Petrol Pump',
    },
    priority: 'high',
    status: 'in_progress',
    instructions: 'Fill sub-base aggregate, compact in 150mm layers, apply cold mix bitumen patch. Install hazard barricades during work.',
    required_evidence: ['Trench measurement photo', 'Bitumen compaction photo', 'Cleaned roadway photo'],
    assigned_to: 'worker-77',
    assigned_at: '2026-10-03T09:00:00Z',
    deadline: '2026-10-03T18:00:00Z',
    sla_hours: 12,
    department: 'Roads & Infrastructure (BBMP)',
    start_time: '2026-10-03T09:45:00Z',
    original_evidence: [
      {
        id: 'ev-2',
        type: 'image',
        url: 'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?auto=format&fit=crop&w=800&q=80',
        mime_type: 'image/jpeg',
        uploaded_at: '2026-10-03T08:45:00Z',
        uploader_id: 'citizen-102',
        source: 'CITIZEN',
        caption: 'Deep trench on 27th Main',
      },
    ],
  },
  {
    id: 'wo-103',
    case_id: 'case-503',
    case_number: 'CC-3998',
    title: 'Streetlight pole electrical sparking in rain',
    description: 'Exposed wire casing at base of pole #B-42 causing sparks during drizzle. Hazardous for school children.',
    location: {
      lat: 12.9295,
      lng: 77.6201,
      address: '14th A Cross, Sector 3, HSR Layout',
      ward: 'Ward 174',
    },
    priority: 'critical',
    status: 'completed',
    instructions: 'Disconnect feeder box, re-insulate underground lead, seal inspection junction box with silicone waterproof gasket.',
    assigned_to: 'worker-77',
    assigned_at: '2026-10-02T14:00:00Z',
    deadline: '2026-10-02T18:00:00Z',
    sla_hours: 4,
    department: 'Electrical / Streetlights (BESCOM)',
    start_time: '2026-10-02T14:30:00Z',
    completion_time: '2026-10-02T16:15:00Z',
    work_note: 'Replaced frayed junction cables and sealed base with weatherproof plate.',
    materials_used: '1x Junction box plate, 5m 6mm insulated copper cable, waterproof silicone sealant.',
    original_evidence: [],
  },
];

const LOCAL_STORAGE_KEY = 'cc:worker_orders';

async function getStoredOrders(): Promise<WorkOrder[]> {
  try {
    const raw = await AsyncStorage.getItem(LOCAL_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return MOCK_WORK_ORDERS;
}

async function persistOrders(orders: WorkOrder[]): Promise<void> {
  try {
    await AsyncStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(orders));
  } catch {}
}

export const workOrdersApi = {
  list: async (): Promise<WorkOrder[]> => {
    try {
      const res = await fetch(`${BASE_URL}/work-orders/my`, {
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) return await res.json();
    } catch {}
    return getStoredOrders();
  },

  get: async (id: string): Promise<WorkOrder | undefined> => {
    try {
      const res = await fetch(`${BASE_URL}/work-orders/${id}`);
      if (res.ok) return await res.json();
    } catch {}
    const list = await getStoredOrders();
    return list.find(w => w.id === id);
  },

  startWork: async (id: string, location: { lat: number; lng: number }): Promise<void> => {
    try {
      await fetch(`${BASE_URL}/work-orders/${id}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location, start_time: new Date().toISOString() }),
      });
    } catch {}

    const list = await getStoredOrders();
    const updated = list.map(w =>
      w.id === id
        ? {
            ...w,
            status: 'in_progress' as const,
            start_time: new Date().toISOString(),
          }
        : w
    );
    await persistOrders(updated);
  },

  uploadEvidence: async (
    id: string,
    evidenceUrls: string[],
    workNote?: string,
    materialsUsed?: string
  ): Promise<void> => {
    try {
      await fetch(`${BASE_URL}/work-orders/${id}/evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          evidence_urls: evidenceUrls,
          work_note: workNote,
          materials_used: materialsUsed,
        }),
      });
    } catch {}

    const list = await getStoredOrders();
    const updated = list.map(w =>
      w.id === id
        ? {
            ...w,
            status: 'evidence_uploaded' as const,
            work_note: workNote,
            materials_used: materialsUsed,
          }
        : w
    );
    await persistOrders(updated);
  },

  complete: async (id: string, completionNote?: string): Promise<void> => {
    try {
      await fetch(`${BASE_URL}/work-orders/${id}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          completion_note: completionNote,
          completion_time: new Date().toISOString(),
        }),
      });
    } catch {}

    const list = await getStoredOrders();
    const updated = list.map(w =>
      w.id === id
        ? {
            ...w,
            status: 'completed' as const,
            completion_time: new Date().toISOString(),
            work_note: completionNote || w.work_note,
          }
        : w
    );
    await persistOrders(updated);
  },
};
