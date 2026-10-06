// API client — switches between real backend and mock based on env
// Pure TypeScript, no native imports

import { mockApi } from './mock/index';
import type { WorkOrder, WorkOrderUpdate, WorkerProfile, KpiSummary, ApiResponse } from './types';

// Use mock by default until real backend is available
const USE_MOCK = true;

export const apiClient = {
  getProfile: async (): Promise<WorkerProfile> => {
    if (USE_MOCK) return mockApi.getProfile();
    throw new Error('Real API not implemented yet');
  },

  getKpi: async (): Promise<KpiSummary> => {
    if (USE_MOCK) return mockApi.getKpi();
    throw new Error('Real API not implemented yet');
  },

  getWorkOrders: async (filter?: { status?: string }): Promise<ApiResponse<WorkOrder[]>> => {
    if (USE_MOCK) return mockApi.getWorkOrders(filter);
    throw new Error('Real API not implemented yet');
  },

  getWorkOrder: async (id: string): Promise<WorkOrder> => {
    if (USE_MOCK) return mockApi.getWorkOrder(id);
    throw new Error('Real API not implemented yet');
  },

  updateWorkOrder: async (id: string, update: WorkOrderUpdate): Promise<WorkOrder> => {
    if (USE_MOCK) return mockApi.updateWorkOrder(id, update);
    throw new Error('Real API not implemented yet');
  },
};
