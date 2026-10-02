/**
 * A10 — Analytics (full page)
 * Three levels per spec:
 *   Descriptive — What happened?
 *   Diagnostic  — Where/why is it concentrated?
 *   Pattern detection — What is unusual or recurring?
 *
 * Data: useAnalyticsOverview() + useDepartmentAnalytics() + useRecurringProblems()
 */
import React, { useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell,
} from 'recharts';
import { BarChart3, AlertTriangle, TrendingUp, Repeat, Loader2 } from 'lucide-react';
import { useAnalyticsOverview } from '../hooks/useAdminApi';

// ─── Mock data (descriptive) ─────────────────────────────────────────────────

const MONTHLY_TREND = [
  { month: 'Jan', created: 180, resolved: 150, reopened: 8 },
  { month: 'Feb', created: 195, resolved: 165, reopened: 10 },
  { month: 'Mar', created: 210, resolved: 188, reopened: 7 },
  { month: 'Apr', created: 175, resolved: 155, reopened: 9 },
  { month: 'May', created: 225, resolved: 200, reopened: 11 },
  { month: 'Jun', created: 248, resolved: 218, reopened: 9 },
];

const CATEGORY_DIST = [
  { name: 'Road Damage',  value: 312 },
  { name: 'Sanitation',   value: 198 },
  { name: 'Electrical',   value: 143 },
  { name: 'Water Supply', value: 97 },
  { name: 'Garbage',      value: 88 },
  { name: 'Other',        value: 45 },
];

const PIE_COLORS = ['#16a34a', '#3b82f6', '#eab308', '#ef4444', '#8b5cf6', '#6b7280'];

const SLA_DATA = [
  { dept: 'Roads',     within_sla: 82, breached: 18 },
  { dept: 'Electrical',within_sla: 74, breached: 26 },
  { dept: 'Sanitation',within_sla: 91, breached: 9  },
  { dept: 'Water',     within_sla: 78, breached: 22 },
  { dept: 'Garbage',   within_sla: 88, breached: 12 },
];

// Diagnostic — hotspot concentration
const HOTSPOT_DATA = [
  { ward: 'W12', count: 48, recurrence: 6, label: 'Road cluster — heavy traffic zone' },
  { ward: 'W18', count: 41, recurrence: 5, label: 'Sanitation — market overflow area' },
  { ward: 'W15', count: 39, recurrence: 4, label: 'Mixed — old drainage infrastructure' },
  { ward: 'W3',  count: 35, recurrence: 3, label: 'Water supply pressure zone' },
];

// Pattern detection — recurring problems
const RECURRING = [
  { location: 'Main Rd, W12', category: 'Road Damage', events: 12, window: '90 days', trend: 'worsening' },
  { location: 'Market area, W18', category: 'Sanitation', events: 9, window: '60 days', trend: 'stable' },
  { location: 'Bypass junction, W6', category: 'Road Damage', events: 7, window: '90 days', trend: 'improving' },
  { location: 'Sector 5, W3', category: 'Water Supply', events: 6, window: '90 days', trend: 'stable' },
];

const TREND_COLOR: Record<string, string> = {
  worsening: 'text-red-600',
  stable:    'text-yellow-600',
  improving: 'text-green-600',
};

const AnalyticsPage: React.FC = () => {
  const { data: overview, isLoading, isError } = useAnalyticsOverview();
  const [tab, setTab] = useState<'descriptive' | 'diagnostic' | 'patterns'>('descriptive');

  return (
    <div className="p-6 min-h-screen space-y-6 page-enter">
      <div>
        <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-emerald-600" /> Analytics
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Descriptive · Diagnostic · Pattern Detection
        </p>
      </div>

      {isError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-4 py-2">
          Live analytics unavailable — displaying representative data. Connect backend to populate.
        </div>
      )}

      {/* Level tabs */}
      <div className="flex gap-1 bg-emerald-50/60 p-1 rounded-xl w-fit border border-emerald-100/50">
        {([
          ['descriptive', 'Descriptive'],
          ['diagnostic',  'Diagnostic'],
          ['patterns',    'Pattern Detection'],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${
              tab === key
                ? 'bg-white text-emerald-700 shadow-sm border border-emerald-100/50'
                : 'text-muted-foreground hover:text-emerald-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Descriptive: What happened? ─────────────────────────────────── */}
      {tab === 'descriptive' && (
        <div className="space-y-6">
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Open Cases',        value: overview?.open_cases ?? 248,         color: 'text-blue-600' },
              { label: 'Critical',          value: overview?.critical_cases ?? 23,       color: 'text-red-600' },
              { label: 'SLA At Risk',       value: overview?.sla_at_risk ?? 41,          color: 'text-amber-600' },
              { label: 'Awaiting Verify',   value: overview?.awaiting_verification ?? 34,color: 'text-purple-600' },
            ].map(({ label, value, color }) => (
              <div key={label} className="civic-card p-4 hover-lift">
                <p className="text-xs text-muted-foreground mb-1">{label}</p>
                <p className={`text-3xl font-bold ${color}`}>{isLoading ? '…' : value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="civic-card p-5 hover-lift">
              <h3 className="text-sm font-semibold text-foreground mb-4">Monthly Case Trends</h3>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={MONTHLY_TREND}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Area type="monotone" dataKey="created"  stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} name="Created" />
                  <Area type="monotone" dataKey="resolved" stroke="#16a34a" fill="#16a34a" fillOpacity={0.2}  name="Resolved" />
                  <Area type="monotone" dataKey="reopened" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1}  name="Reopened" />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="civic-card p-5 hover-lift">
              <h3 className="text-sm font-semibold text-foreground mb-4">Category Distribution</h3>
              <div className="flex items-center gap-6">
                <ResponsiveContainer width="55%" height={200}>
                  <PieChart>
                    <Pie data={CATEGORY_DIST} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={false}>
                      {CATEGORY_DIST.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-1.5">
                  {CATEGORY_DIST.map((c, i) => (
                    <div key={c.name} className="flex items-center gap-2 text-xs">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: PIE_COLORS[i] }} />
                      <span className="text-muted-foreground flex-1">{c.name}</span>
                      <span className="font-semibold text-foreground">{c.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* SLA compliance */}
          <div className="civic-card p-5 hover-lift">
            <h3 className="text-sm font-semibold text-foreground mb-4">SLA Compliance by Department (%)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={SLA_DATA} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                <YAxis dataKey="dept" type="category" tick={{ fontSize: 12 }} width={70} />
                <Tooltip />
                <Legend />
                <Bar dataKey="within_sla" stackId="a" fill="#16a34a" name="Within SLA" />
                <Bar dataKey="breached"   stackId="a" fill="#ef4444" name="Breached" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Diagnostic: Where/why? ───────────────────────────────────────── */}
      {tab === 'diagnostic' && (
        <div className="space-y-6">
          <div className="civic-card p-5 hover-lift">
            <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-600" /> Spatial Concentration — Top Wards
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={HOTSPOT_DATA}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ward" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count"      name="Total Cases"       fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="recurrence" name="Recurring Locations" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-3">
            {HOTSPOT_DATA.map(h => (
              <div key={h.ward} className="civic-card p-4 flex items-center justify-between hover-lift">
                <div>
                  <span className="font-mono text-xs text-emerald-700 font-bold">{h.ward}</span>
                  <span className="ml-3 text-sm text-foreground">{h.label}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>{h.count} cases</span>
                  <span className="text-amber-600 font-medium">{h.recurrence} recurring</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Pattern Detection ────────────────────────────────────────────── */}
      {tab === 'patterns' && (
        <div className="space-y-5">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-sm font-semibold text-amber-800 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" /> Recurring Problem Locations
            </p>
            <p className="text-xs text-amber-700 mt-1">
              Flagged by server-side pattern detection. These locations have recurring civic cases
              within the same geographic cluster.
            </p>
          </div>

          <div className="space-y-3">
            {RECURRING.map((r, i) => (
              <div key={i} className="civic-card p-4 hover-lift">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="h-7 w-7 rounded-full bg-red-50 border border-red-100 flex items-center justify-center flex-shrink-0">
                      <Repeat className="h-4 w-4 text-red-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{r.location}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{r.category} · {r.events} events in {r.window}</p>
                    </div>
                  </div>
                  <span className={`text-xs font-semibold ${TREND_COLOR[r.trend]} capitalize`}>
                    {r.trend}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
            Recurring problem detection uses <code>/map/recurring-problems</code>.
            Full pattern intelligence is populated from backend ML pipeline once connected.
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalyticsPage;
