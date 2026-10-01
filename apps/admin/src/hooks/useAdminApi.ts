/**
 * CivicConnect v2 — Admin API Hooks
 *
 * React Query hooks that wrap the Section 51A API client.
 * Components use these hooks; they never call the api.ts functions directly.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  casesApi,
  triageApi,
  analyticsApi,
  mapApi,
  incidentsApi,
  copilotApi,
  authApi,
  CasesQuery,
  MapQuery,
} from '../lib/api';

// ─── Cases ────────────────────────────────────────────────────────────────────

export function useCases(params: CasesQuery = {}) {
  return useQuery({
    queryKey: ['cases', params],
    queryFn: () => casesApi.list(params),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

export function useCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ['case', caseId],
    queryFn: () => casesApi.get(caseId!),
    enabled: Boolean(caseId),
    staleTime: 30_000,
  });
}

export function useCaseTimeline(caseId: string | undefined) {
  return useQuery({
    queryKey: ['case-timeline', caseId],
    queryFn: () => casesApi.timeline(caseId!),
    enabled: Boolean(caseId),
    staleTime: 15_000,
  });
}

export function usePatchCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, body }: { caseId: string; body: Parameters<typeof casesApi.patch>[1] }) =>
      casesApi.patch(caseId, body),
    onSuccess: (_, { caseId }) => {
      qc.invalidateQueries({ queryKey: ['case', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
  });
}

export function useCreateWorkOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      caseId,
      body,
    }: {
      caseId: string;
      body: Parameters<typeof casesApi.createWorkOrder>[1];
    }) => casesApi.createWorkOrder(caseId, body),
    onSuccess: (_, { caseId }) => {
      qc.invalidateQueries({ queryKey: ['case', caseId] });
    },
  });
}

export function useFusionAnalyze() {
  return useMutation({
    mutationFn: (caseId: string) => casesApi.fusionAnalyze(caseId),
  });
}

// ─── AI Triage ────────────────────────────────────────────────────────────────

export function useTriageAnalyze() {
  return useMutation({
    mutationFn: (caseId: string) => triageApi.analyze(caseId),
  });
}

export function useTriageDecide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      caseId,
      body,
    }: {
      caseId: string;
      body: Parameters<typeof triageApi.decide>[1];
    }) => triageApi.decide(caseId, body),
    onSuccess: (_, { caseId }) => {
      qc.invalidateQueries({ queryKey: ['case', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
  });
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export function useAnalyticsOverview() {
  return useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: () => analyticsApi.overview(),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function useDepartmentAnalytics(departmentId: string | undefined) {
  return useQuery({
    queryKey: ['analytics', 'department', departmentId],
    queryFn: () => analyticsApi.department(departmentId!),
    enabled: Boolean(departmentId),
    staleTime: 60_000,
  });
}

export function useIncidentsAnalytics() {
  return useQuery({
    queryKey: ['analytics', 'incidents'],
    queryFn: () => analyticsApi.incidents(),
    staleTime: 60_000,
  });
}

// ─── Map / Geospatial ─────────────────────────────────────────────────────────

export function useMapCases(params: MapQuery = {}) {
  return useQuery({
    queryKey: ['map-cases', params],
    queryFn: () => mapApi.cases(params),
    staleTime: 30_000,
  });
}

export function useMapHotspots() {
  return useQuery({
    queryKey: ['map-hotspots'],
    queryFn: () => mapApi.hotspots(),
    staleTime: 120_000,
  });
}

export function useRecurringProblems() {
  return useQuery({
    queryKey: ['recurring-problems'],
    queryFn: () => mapApi.recurringProblems(),
    staleTime: 120_000,
  });
}

// ─── Incidents ────────────────────────────────────────────────────────────────

export function useIncident(incidentId: string | undefined) {
  return useQuery({
    queryKey: ['incident', incidentId],
    queryFn: () => incidentsApi.get(incidentId!),
    enabled: Boolean(incidentId),
    staleTime: 30_000,
  });
}

export function useCreateIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof incidentsApi.create>[0]) =>
      incidentsApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['analytics', 'incidents'] });
    },
  });
}

// ─── Copilot ──────────────────────────────────────────────────────────────────

export function useCopilotQuery() {
  return useMutation({
    mutationFn: ({
      query,
      scope,
    }: {
      query: string;
      scope?: Parameters<typeof copilotApi.query>[1];
    }) => copilotApi.query(query, scope),
  });
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => authApi.me(),
    staleTime: 300_000,
    retry: false,
  });
}
