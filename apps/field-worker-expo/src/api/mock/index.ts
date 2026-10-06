// Mock API implementation — returns data with realistic delay
// Falls back to this when backend is unavailable

import type { WorkOrder, WorkOrderUpdate, WorkerProfile, KpiSummary, ApiResponse } from '../types';
import { MOCK_WORKER, MOCK_WORK_ORDERS, MOCK_KPI } from './data';

const delay = (ms: number) => new Promise<void>(res => setTimeout(res, ms));

// In-memory store so updates persist within a session
let workOrders = [...MOCK_WORK_ORDERS];

export const mockApi = {
  getProfile: async (): Promise<WorkerProfile> => {
    await delay(300);
    return { ...MOCK_WORKER };
  },

  getKpi: async (): Promise<KpiSummary> => {
    await delay(200);
    const openCount = workOrders.filter(w => w.status === 'OPEN' || w.status === 'IN_PROGRESS').length;
    const doneToday = workOrders.filter(w => w.status === 'DONE').length;
    const now = Date.now();
    const overdueCount = workOrders.filter(w =>
      (w.status === 'OPEN' || w.status === 'IN_PROGRESS') &&
      new Date(w.slaDeadline).getTime() < now
    ).length;
    return {
      ...MOCK_KPI,
      openCount,
      doneToday,
      overdueCount,
    };
  },

  getWorkOrders: async (filter?: { status?: string }): Promise<ApiResponse<WorkOrder[]>> => {
    await delay(400);
    let results = [...workOrders];
    if (filter?.status) {
      const s = filter.status.toUpperCase();
      if (s === 'DONE') {
        results = results.filter(w => w.status === 'DONE' || w.status === 'CANCELLED');
      } else {
        results = results.filter(w => w.status !== 'DONE' && w.status !== 'CANCELLED');
      }
    }
    return {
      data: results,
      meta: { page: 1, pageSize: results.length, total: results.length },
    };
  },

  getWorkOrder: async (id: string): Promise<WorkOrder> => {
    await delay(250);
    const wo = workOrders.find(w => w.id === id);
    if (!wo) throw new Error(`Work order ${id} not found`);
    return { ...wo };
  },

  updateWorkOrder: async (id: string, update: WorkOrderUpdate): Promise<WorkOrder> => {
    await delay(500);
    const idx = workOrders.findIndex(w => w.id === id);
    if (idx === -1) throw new Error(`Work order ${id} not found`);
    const now = new Date().toISOString();
    workOrders[idx] = {
      ...workOrders[idx],
      ...update,
      updatedAt: now,
      ...(update.status === 'DONE' ? { closedAt: now } : {}),
    };
    return { ...workOrders[idx] };
  },

  resetStore: () => {
    workOrders = [...MOCK_WORK_ORDERS];
  },
};
