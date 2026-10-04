/**
 * A07 — Department Performance
 * Four highlight cards, one metrics table with SLA meters and workload bars,
 * a caution note about comparing unequal workloads.
 *
 * Data: /analytics/departments (and /{id} for a drawer).
 * Meters computed in the client.
 */
import React, { useState } from 'react';
import { Building2, TrendingDown, TrendingUp, AlertCircle, Clock, RotateCcw } from 'lucide-react';

const DEPARTMENTS = [
  { id: 'roads', name: 'Road & Transportation' },
  { id: 'electrical', name: 'Electrical' },
  { id: 'sanitation', name: 'Sanitation' },
  { id: 'water', name: 'Water Works' },
  { id: 'garbage', name: 'Garbage Management' },
];

const MOCK_PERF: Record<string, {
  incoming: number; active: number; resolved: number;
  median_resolution_hours: number; sla_compliance_pct: number;
  reopened: number; backlog_age_days: number;
}> = {
  roads:      { incoming: 89, active: 23, resolved: 66, median_resolution_hours: 31, sla_compliance_pct: 82, reopened: 4, backlog_age_days: 8 },
  electrical: { incoming: 76, active: 18, resolved: 58, median_resolution_hours: 42, sla_compliance_pct: 74, reopened: 6, backlog_age_days: 11 },
  sanitation: { incoming: 54, active: 12, resolved: 42, median_resolution_hours: 22, sla_compliance_pct: 91, reopened: 2, backlog_age_days: 5 },
  water:      { incoming: 61, active: 20, resolved: 41, median_resolution_hours: 38, sla_compliance_pct: 78, reopened: 5, backlog_age_days: 9 },
  garbage:    { incoming: 48, active: 15, resolved: 33, median_resolution_hours: 19, sla_compliance_pct: 88, reopened: 1, backlog_age_days: 4 },
};

// Aggregate highlight cards
const totalIncoming = Object.values(MOCK_PERF).reduce((s, d) => s + d.incoming, 0);
const totalResolved = Object.values(MOCK_PERF).reduce((s, d) => s + d.resolved, 0);
const avgSla = Math.round(Object.values(MOCK_PERF).reduce((s, d) => s + d.sla_compliance_pct, 0) / Object.keys(MOCK_PERF).length);
const totalReopened = Object.values(MOCK_PERF).reduce((s, d) => s + d.reopened, 0);

const DepartmentPerformancePage: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A07</div>
        <h1 className="cc-title cc-headline-pop">Performance</h1>
      </div>

      {/* Four highlight cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Incoming', value: totalIncoming, icon: TrendingUp, sub: 'last 30 days' },
          { label: 'Total Resolved', value: totalResolved, icon: TrendingDown, sub: 'last 30 days' },
          { label: 'Avg SLA Compliance', value: `${avgSla}%`, icon: Clock, sub: 'across departments', pulse: avgSla < 80 },
          { label: 'Reopened', value: totalReopened, icon: RotateCcw, sub: 'total', pulse: totalReopened > 10 },
        ].map((kpi, i) => {
          const Icon = kpi.icon;
          return (
            <div key={kpi.label} className={`cc-kpi-card cc-card-lift cc-fade-up ${kpi.pulse ? 'cc-kpi-pulse' : ''}`}
              style={{ '--stagger-index': i } as React.CSSProperties}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
                  <Icon className="h-3.5 w-3.5 text-ink" />
                </div>
              </div>
              <p className="cc-kpi-value">{kpi.value}</p>
              <p className="cc-kpi-label">{kpi.label}</p>
              <p className="cc-kpi-sub">{kpi.sub}</p>
            </div>
          );
        })}
      </div>

      {/* Metrics table with SLA meters and workload bars */}
      <div className="cc-card cc-fade-up" style={{ '--stagger-index': 4 } as React.CSSProperties}>
        <div className="px-5 py-3 border-b-2 border-ink">
          <h3 className="font-display text-sm text-ink">Department Metrics</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
            <thead>
              <tr>
                <th>Department</th>
                <th>Incoming</th>
                <th>Active</th>
                <th>Resolved</th>
                <th>Median Hours</th>
                <th>SLA</th>
                <th>Workload</th>
                <th>Reopened</th>
              </tr>
            </thead>
            <tbody>
              {DEPARTMENTS.map((dept, i) => {
                const perf = MOCK_PERF[dept.id];
                const workloadPct = Math.min((perf.incoming / 100) * 100, 100);
                return (
                  <tr key={dept.id} className="cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
                    <td className="font-semibold text-ink">{dept.name}</td>
                    <td className="font-mono text-sm">{perf.incoming}</td>
                    <td className="font-mono text-sm">{perf.active}</td>
                    <td className="font-mono text-sm">{perf.resolved}</td>
                    <td className="font-mono text-sm">{perf.median_resolution_hours}h</td>
                    <td style={{ minWidth: '120px' }}>
                      <div className="flex items-center gap-2">
                        <div className="cc-meter flex-1">
                          <div
                            className={`cc-meter-fill cc-bar-grow-x ${perf.sla_compliance_pct >= 80 ? 'cc-meter-fill-lime' : 'cc-meter-fill-risk'}`}
                            style={{ width: `${perf.sla_compliance_pct}%`, '--stagger-index': i } as React.CSSProperties}
                          />
                        </div>
                        <span className="text-xs font-mono w-8 text-right">{perf.sla_compliance_pct}%</span>
                      </div>
                    </td>
                    <td style={{ minWidth: '100px' }}>
                      <div className="cc-meter">
                        <div
                          className={`cc-meter-fill cc-bar-grow-x ${workloadPct >= 80 ? 'cc-meter-fill-risk' : 'cc-meter-fill-lime'}`}
                          style={{ width: `${workloadPct}%`, '--stagger-index': i } as React.CSSProperties}
                        />
                      </div>
                    </td>
                    <td className="font-mono text-sm">
                      <span className={perf.reopened > 3 ? 'text-fire font-semibold' : 'text-muted'}>{perf.reopened}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Caution note per the plan */}
      <div className="cc-banner-degraded cc-fade-up" style={{ '--stagger-index': 5 } as React.CSSProperties}>
        <AlertCircle className="h-4 w-4 shrink-0" />
        <p className="text-xs">
          Caution: comparing departments with unequal workloads may be misleading. Road & Transportation handles 2x the volume of Garbage Management.
          SLA targets also differ by category complexity.
        </p>
      </div>
    </div>
  );
};

export default DepartmentPerformancePage;
