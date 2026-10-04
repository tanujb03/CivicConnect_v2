/**
 * A02 — Operations Dashboard
 * Answers: "What needs municipal attention now?"
 *
 * Data: useAnalyticsOverview() — isolates backend via hook.
 * Currently falls back to mock data while backend is not yet ready.
 *
 * Plan spec: Header with pill nav, ticker, six KPI cards, AI summary panel
 * plus map, priority queue under folder tabs, incident board, charts row.
 *
 * Endpoints: /analytics/overview (KPIs, daily_trend),
 *   POST /analytics/explain (AI panel, show warnings),
 *   GET /cases?sort=priority (queue),
 *   /analytics/incidents, /analytics/hotspots,
 *   /analytics/departments, /analytics/wards.
 */
import React, { useState } from 'react';
import {
  ArrowUpRight, ArrowDownRight, FileText, Clock, AlertCircle,
  TrendingUp, RotateCcw, Brain, MapPin, Loader2, Users,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line,
} from 'recharts';
import CityMap from '../components/CityMap';
import WardHeatmap from '../components/WardHeatmap';
import DepartmentPerformance from '../components/DepartmentPerformance';
import RecentIssuesTable from '../components/RecentIssuesTable';
import { useAnalyticsOverview } from '../hooks/useAdminApi';

// ─── Mock data — replaced by API when backend is ready ────────────────────────
const mockKpis = [
  { title: 'Active Cases',          value: 248,   change: '+12',  trend: 'up',   icon: FileText,    pulse: false },
  { title: 'Critical Cases',        value: 23,    change: '+5',   trend: 'up',   icon: AlertCircle, pulse: true },
  { title: 'SLA At Risk',           value: 41,    change: '+8',   trend: 'up',   icon: Clock,       pulse: true },
  { title: 'Unassigned',            value: 17,    change: '-3',   trend: 'down', icon: TrendingUp,  pulse: false },
  { title: 'Awaiting Verification', value: 34,    change: '+2',   trend: 'up',   icon: Users,       pulse: false },
  { title: 'Reopened',              value: 9,     change: '+1',   trend: 'up',   icon: RotateCcw,   pulse: true },
];

const mockPriorityQueue = [
  { id: 'CC-1042', title: 'Major pothole near school — recurring', priority: 'URGENT', ward: 'W12', age: '5d', dept: 'Roads' },
  { id: 'CC-1038', title: 'Raw sewage overflow, residential block', priority: 'HIGH',   ward: 'W18', age: '3d', dept: 'Sanitation' },
  { id: 'CC-1031', title: 'Street lighting failure — 200m stretch', priority: 'HIGH',   ward: 'W7',  age: '6d', dept: 'Electrical' },
  { id: 'CC-1027', title: 'Water supply disruption — 300 households', priority: 'URGENT', ward: 'W3', age: '2d', dept: 'Water' },
  { id: 'CC-1019', title: 'Garbage accumulation — market area',     priority: 'NORMAL', ward: 'W9',  age: '4d', dept: 'Sanitation' },
];

const aiSituationSummary =
  'Road-related cases are concentrated in W12 and W18 (31 in 7 days, 19 within 800 m). Three locations have recurring reports. Sanitation backlog in W18 is 27% above the 30-day baseline.';

const trendData = [
  { month: 'Jan', resolved: 120, pending: 45 },
  { month: 'Feb', resolved: 135, pending: 38 },
  { month: 'Mar', resolved: 150, pending: 42 },
  { month: 'Apr', resolved: 142, pending: 35 },
  { month: 'May', resolved: 165, pending: 28 },
  { month: 'Jun', resolved: 178, pending: 23 },
];

const categoryData = [
  { name: 'Potholes', value: 145 },
  { name: 'Lighting', value: 89 },
  { name: 'Garbage', value: 76 },
  { name: 'Water', value: 54 },
  { name: 'Drainage', value: 43 },
];

const TICKER_ITEMS = [
  'W12 hotspot alert — 31 road cases in 7 days',
  'SLA breach approaching: CC-1042, CC-1031, CC-1027',
  'Sanitation backlog in W18 is 27% above baseline',
  '12 new cases in last hour',
  'Field crew dispatched to W07 lighting failure',
];

// ─── Priority chip per the plan ───────────────────────────────────────────────
function PriorityChip({ priority }: { priority: string }) {
  const cls: Record<string, string> = {
    URGENT: 'cc-priority-urgent',
    HIGH:   'cc-priority-high',
    NORMAL: 'cc-priority-normal',
    LOW:    'cc-priority-low',
  };
  return (
    <span className={`cc-chip text-[11px] ${cls[priority] ?? 'cc-priority-normal'}`}>
      {priority}
    </span>
  );
}

// Recharts custom tooltip styled with tokens
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload) return null;
  return (
    <div className="cc-card p-3 text-xs" style={{ boxShadow: 'var(--shadow-hard)' }}>
      <p className="font-mono font-semibold text-ink mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} style={{ color: entry.color }} className="font-medium">
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
};

// ─── Dashboard ────────────────────────────────────────────────────────────────

const Dashboard: React.FC = () => {
  const { data: overview, isLoading, isError } = useAnalyticsOverview();
  const [activeTab, setActiveTab] = useState('all');

  return (
    <div className="space-y-8">

      {/* ── Page Header with eyebrow ──────────────────────────────────────── */}
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A02</div>
        <h1 className="cc-title cc-headline-pop">Operations</h1>
        <div className="flex items-center gap-3 mt-3">
          {isLoading && (
            <div className="cc-chip cc-chip-dashed text-[10px]">
              <Loader2 className="h-3 w-3 animate-spin" /> Syncing...
            </div>
          )}
        </div>
      </div>

      {/* ── Ticker ────────────────────────────────────────────────────────── */}
      <div className="cc-ticker border-2 border-ink rounded-md py-2 -mx-1">
        <div className="cc-ticker-track gap-10 px-4">
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
            <span key={i} className="flex items-center gap-2 text-muted text-xs font-mono whitespace-nowrap shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-fire shrink-0" />
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* ── Error state banner ────────────────────────────────────────────── */}
      {isError && (
        <div className="cc-banner-degraded">
          <AlertCircle className="w-4 h-4 shrink-0" />
          Live data unavailable — showing cached figures. Backend not yet connected.
        </div>
      )}

      {/* ── Six KPI Cards ─────────────────────────────────────────────────── */}
      <section>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          {mockKpis.map((kpi, i) => {
            const Icon = kpi.icon;
            const isDown = kpi.trend === 'down';
            return (
              <div
                key={i}
                className={`cc-kpi-card cc-card-lift cc-fade-up ${kpi.pulse ? 'cc-kpi-pulse' : ''}`}
                style={{ '--stagger-index': i } as React.CSSProperties}
              >
                <div className="flex items-start justify-between mb-3">
                  <div
                    className="w-9 h-9 rounded-md border-2 border-ink flex items-center justify-center"
                    style={{ background: kpi.pulse ? 'var(--fire)' : 'var(--lime-tint)' }}
                  >
                    <Icon className="h-4 w-4" style={{ color: kpi.pulse ? 'var(--on-fire)' : 'var(--ink)' }} />
                  </div>
                  {isDown
                    ? <ArrowDownRight className="h-4 w-4" style={{ color: 'var(--lime)' }} />
                    : <ArrowUpRight className="h-4 w-4" style={{ color: kpi.pulse ? 'var(--fire)' : 'var(--muted)' }} />}
                </div>
                {/* KPI counter — counts from 0 in 1.8s via CSS @property */}
                <p className="cc-kpi-value">{kpi.value}</p>
                <p className="cc-kpi-label">{kpi.title}</p>
                <p className={`text-xs font-semibold mt-1.5 font-mono ${kpi.pulse ? 'text-fire' : isDown ? 'text-lime' : 'text-muted'}`}>
                  {kpi.change} this week
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── AI Situation Summary (wine panel with rosette) ─────────────── */}
      <section className="cc-ai-panel cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
        <div className="flex items-start gap-4">
          {/* Rosette badge */}
          <div className="relative shrink-0">
            <div
              className="w-10 h-10 rounded-md border-2 border-on-wine/30 flex items-center justify-center"
              style={{ background: 'var(--rust-deep)' }}
            >
              <Brain className="h-5 w-5 text-on-wine" />
            </div>
            <div
              className="absolute inset-[-6px] rounded-xl border-2 border-dashed border-on-wine/20 cc-rosette pointer-events-none"
              aria-hidden="true"
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-sm font-display text-on-wine">AI Situation Summary</h3>
              {/* AI badge is dashed per the plan: AI suggestions = dashed chips */}
              <span className="cc-chip cc-chip-dashed text-[10px] border-on-wine/40 text-on-wine/80">
                AI Generated
              </span>
            </div>
            {/* Typed AI lines effect */}
            <div className="space-y-1">
              {aiSituationSummary.split('. ').map((sentence, i) => (
                <p
                  key={i}
                  className="cc-typed-line text-sm text-on-wine/80 leading-relaxed"
                  style={{ '--line-index': i } as React.CSSProperties}
                >
                  {sentence}{i < aiSituationSummary.split('. ').length - 1 ? '.' : ''}
                </p>
              ))}
            </div>
            <p className="mt-3 text-xs text-on-wine/40 font-mono">
              Backed by case database — click any linked case to verify.
            </p>
          </div>
        </div>
      </section>

      {/* ── Priority Queue under Folder Tabs ──────────────────────────────── */}
      <section className="cc-fade-up" style={{ '--stagger-index': 3 } as React.CSSProperties}>
        {/* Folder tabs */}
        <div className="cc-folder-tabs">
          {[
            { id: 'all', label: 'All Priority', count: 5 },
            { id: 'critical', label: 'Critical', count: 2 },
            { id: 'sla', label: 'SLA at Risk', count: 3 },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`cc-folder-tab ${activeTab === tab.id ? 'cc-folder-tab-active' : ''}`}
            >
              {tab.label}
              <span className="ml-2 cc-chip text-[9px] py-0 px-1.5 border-ink/30">
                {tab.count}
              </span>
            </button>
          ))}
        </div>
        {/* Queue table */}
        <div className="cc-card" style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0, borderTop: 'none' }}>
          <div className="overflow-x-auto">
            <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Title</th>
                  <th>Priority</th>
                  <th>Ward</th>
                  <th>Dept.</th>
                  <th>Age</th>
                </tr>
              </thead>
              <tbody>
                {mockPriorityQueue.map((item, i) => (
                  <tr
                    key={item.id}
                    className="cc-fade-up cursor-pointer"
                    style={{ '--stagger-index': i } as React.CSSProperties}
                  >
                    <td className="font-mono text-xs font-semibold" style={{ color: 'var(--wine)' }}>{item.id}</td>
                    <td className="max-w-xs truncate">{item.title}</td>
                    <td><PriorityChip priority={item.priority} /></td>
                    <td className="font-mono text-muted">{item.ward}</td>
                    <td className="text-muted">{item.dept}</td>
                    <td className="font-mono text-muted">{item.age}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-5 py-3 border-t-2 border-ink flex justify-end">
            <button className="cc-btn cc-btn-outline text-xs py-1.5 px-3">
              View Full Workbench <ArrowUpRight className="h-3 w-3" />
            </button>
          </div>
        </div>
      </section>

      {/* ── City Map Widget ───────────────────────────────────────────────── */}
      <section className="cc-fade-up" style={{ '--stagger-index': 4 } as React.CSSProperties}>
        <CityMap />
      </section>

      {/* ── Ward Heatmap + Department Performance ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 cc-fade-up" style={{ '--stagger-index': 5 } as React.CSSProperties}>
          <WardHeatmap />
        </div>
        <div className="lg:col-span-1 cc-fade-up" style={{ '--stagger-index': 6 } as React.CSSProperties}>
          <DepartmentPerformance />
        </div>
      </div>

      {/* ── Recent Issues Table ────────────────────────────────────────────── */}
      <section className="cc-fade-up" style={{ '--stagger-index': 7 } as React.CSSProperties}>
        <RecentIssuesTable />
      </section>

      {/* ── Analytics Charts Row ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Resolution Trends */}
        <div className="cc-card p-6 cc-card-lift cc-fade-up" style={{ '--stagger-index': 8 } as React.CSSProperties}>
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center"
              style={{ background: 'var(--lime-tint)' }}
            >
              <TrendingUp className="h-3.5 w-3.5 text-ink" />
            </div>
            <h3 className="text-sm font-display text-ink">Resolution Trends</h3>
          </div>
          <p className="text-xs font-mono text-muted mb-4">Monthly resolved vs pending</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--dot)" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--muted)', fontFamily: 'var(--font-mono)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--muted)', fontFamily: 'var(--font-mono)' }} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="resolved" stroke="var(--lime)" strokeWidth={2.5} dot={false} name="Resolved" />
              <Line type="monotone" dataKey="pending"  stroke="var(--fire)" strokeWidth={2.5} dot={false} name="Pending" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Top Issue Categories */}
        <div className="cc-card p-6 cc-card-lift cc-fade-up" style={{ '--stagger-index': 9 } as React.CSSProperties}>
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center"
              style={{ background: 'var(--lime-tint)' }}
            >
              <MapPin className="h-3.5 w-3.5 text-ink" />
            </div>
            <h3 className="text-sm font-display text-ink">Top Issue Categories</h3>
          </div>
          <p className="text-xs font-mono text-muted mb-4">Distribution by category</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--dot)" />
              <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--muted)', fontFamily: 'var(--font-mono)' }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: 'var(--ink)', fontFamily: 'var(--font-mono)' }} width={70} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" fill="var(--wine)" radius={[0, 4, 4, 0]} name="Cases" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
