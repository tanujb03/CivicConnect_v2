/**
 * A07 — Department Performance
 * Metrics: incoming workload, active, resolved, median resolution time,
 * SLA compliance, reopened, backlog age, recurring cases, workload by severity.
 *
 * Avoids simplistic rankings that ignore workload composition (per spec).
 * Data: useDepartmentAnalytics() — /analytics/departments/:id
 */
import React, { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend,
} from 'recharts';
import { Building2, TrendingDown, TrendingUp, AlertCircle, Clock, RotateCcw } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const DEPARTMENTS = [
  { id: 'roads',       name: 'Road & Transportation' },
  { id: 'electrical',  name: 'Electrical' },
  { id: 'sanitation',  name: 'Sanitation' },
  { id: 'water',       name: 'Water Works' },
  { id: 'garbage',     name: 'Garbage Management' },
];

const MOCK_PERF: Record<string, {
  incoming: number; active: number; resolved: number;
  median_resolution_hours: number; sla_compliance_pct: number;
  reopened: number; backlog_age_days: number;
  by_severity: { severity: string; count: number }[];
}> = {
  roads:     { incoming: 89, active: 23, resolved: 66, median_resolution_hours: 31, sla_compliance_pct: 82, reopened: 4, backlog_age_days: 8, by_severity: [{ severity: 'CRITICAL', count: 5 }, { severity: 'HIGH', count: 12 }, { severity: 'MEDIUM', count: 28 }, { severity: 'LOW', count: 21 }] },
  electrical:{ incoming: 76, active: 18, resolved: 58, median_resolution_hours: 42, sla_compliance_pct: 74, reopened: 6, backlog_age_days: 11, by_severity: [{ severity: 'CRITICAL', count: 3 }, { severity: 'HIGH', count: 9 }, { severity: 'MEDIUM', count: 31 }, { severity: 'LOW', count: 15 }] },
  sanitation:{ incoming: 54, active: 12, resolved: 42, median_resolution_hours: 22, sla_compliance_pct: 91, reopened: 2, backlog_age_days: 5, by_severity: [{ severity: 'CRITICAL', count: 1 }, { severity: 'HIGH', count: 7 }, { severity: 'MEDIUM', count: 22 }, { severity: 'LOW', count: 12 }] },
  water:     { incoming: 61, active: 20, resolved: 41, median_resolution_hours: 38, sla_compliance_pct: 78, reopened: 5, backlog_age_days: 9, by_severity: [{ severity: 'CRITICAL', count: 8 }, { severity: 'HIGH', count: 14 }, { severity: 'MEDIUM', count: 19 }, { severity: 'LOW', count: 8 }] },
  garbage:   { incoming: 48, active: 15, resolved: 33, median_resolution_hours: 19, sla_compliance_pct: 88, reopened: 1, backlog_age_days: 4, by_severity: [{ severity: 'CRITICAL', count: 0 }, { severity: 'HIGH', count: 4 }, { severity: 'MEDIUM', count: 18 }, { severity: 'LOW', count: 11 }] },
};

const ALL_PERF_COMPARISON = DEPARTMENTS.map(d => ({
  dept: d.name.split(' ')[0],
  SLA:           MOCK_PERF[d.id].sla_compliance_pct,
  ResolutionTime: 100 - (MOCK_PERF[d.id].median_resolution_hours / 48) * 100,
  Workload:      Math.min((MOCK_PERF[d.id].incoming / 100) * 100, 100),
}));

function MetricCard({ label, value, icon: Icon, sub, highlight }: {
  label: string; value: string | number; icon: React.ElementType;
  sub?: string; highlight?: 'good' | 'warn' | 'bad';
}) {
  const colors = { good: 'text-green-600', warn: 'text-yellow-600', bad: 'text-red-600' };
  return (
    <div className="civic-card p-4 rounded-xl border border-gray-100">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="h-4 w-4 text-green-600" />
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${highlight ? colors[highlight] : 'text-gray-900'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  MEDIUM:   '#eab308',
  LOW:      '#22c55e',
};

const DepartmentPerformancePage: React.FC = () => {
  const [selectedDept, setSelectedDept] = useState('roads');
  const perf = MOCK_PERF[selectedDept];

  const slaColor = perf.sla_compliance_pct >= 85 ? 'good' : perf.sla_compliance_pct >= 70 ? 'warn' : 'bad';

  return (
    <div className="p-6 bg-civic-bg min-h-screen space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Department Performance</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Workload-adjusted metrics — avoids simplistic rankings that ignore case complexity.
          </p>
        </div>
        <Select value={selectedDept} onValueChange={setSelectedDept}>
          <SelectTrigger className="w-56">
            <Building2 className="h-4 w-4 mr-2 text-green-600" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DEPARTMENTS.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-4">
        <MetricCard label="Incoming (30d)"    value={perf.incoming}                          icon={TrendingUp} />
        <MetricCard label="Active"             value={perf.active}                            icon={AlertCircle} highlight="warn" />
        <MetricCard label="Resolved (30d)"     value={perf.resolved}                          icon={TrendingDown} highlight="good" />
        <MetricCard label="Median Resolution"  value={`${perf.median_resolution_hours}h`}     icon={Clock} />
        <MetricCard label="SLA Compliance"     value={`${perf.sla_compliance_pct}%`}          icon={Clock} highlight={slaColor} sub="target ≥ 85%" />
        <MetricCard label="Reopened"           value={perf.reopened}                          icon={RotateCcw} highlight={perf.reopened > 5 ? 'bad' : 'good'} />
        <MetricCard label="Backlog Avg Age"    value={`${perf.backlog_age_days}d`}            icon={Clock} highlight={perf.backlog_age_days > 10 ? 'bad' : perf.backlog_age_days > 7 ? 'warn' : 'good'} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Workload by severity */}
        <div className="civic-card p-5 rounded-xl border border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Workload by Severity</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={perf.by_severity}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="severity" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar
                dataKey="count"
                name="Cases"
                radius={[4, 4, 0, 0]}
                fill="#16a34a"
                label={{ position: 'top', fontSize: 11 }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Cross-department radar */}
        <div className="civic-card p-5 rounded-xl border border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Cross-Department Comparison</h3>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={ALL_PERF_COMPARISON}>
              <PolarGrid />
              <PolarAngleAxis dataKey="dept" tick={{ fontSize: 11 }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
              <Radar name="SLA %"       dataKey="SLA"           stroke="#16a34a" fill="#16a34a" fillOpacity={0.3} />
              <Radar name="Resolution"  dataKey="ResolutionTime" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-gray-400 mt-2 italic text-center">
            Resolution score = inverse of median resolution time (normalised)
          </p>
        </div>
      </div>

      {/* Recurring cases note */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
        <p className="font-semibold mb-1">Recurring cases in {DEPARTMENTS.find(d => d.id === selectedDept)?.name}</p>
        <p className="text-xs text-amber-700">
          Pattern detection and recurring-problem flagging will be populated from <code>/map/recurring-problems</code> once the backend analytics pipeline is connected.
        </p>
      </div>
    </div>
  );
};

export default DepartmentPerformancePage;
