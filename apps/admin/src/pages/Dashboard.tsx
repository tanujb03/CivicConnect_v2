/**
 * A02 — Operations Dashboard
 * Answers: "What needs municipal attention now?"
 *
 * Data: useAnalyticsOverview() — isolates backend via hook.
 * Currently falls back to mock data while backend is not yet ready.
 */
import React from 'react';
import {
  ArrowUpRight, ArrowDownRight, Users, FileText, Clock, AlertCircle,
  TrendingUp, RotateCcw, Brain, MapPin, Loader2, Sparkles
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
  { title: 'Active Cases',         value: '248',    change: '+12',  trend: 'up',   icon: FileText,    danger: false },
  { title: 'Critical Cases',       value: '23',     change: '+5',   trend: 'up',   icon: AlertCircle, danger: true },
  { title: 'SLA At Risk',          value: '41',     change: '+8',   trend: 'up',   icon: Clock,       danger: true },
  { title: 'Unassigned',           value: '17',     change: '-3',   trend: 'down', icon: TrendingUp,  danger: false },
  { title: 'Awaiting Verification',value: '34',     change: '+2',   trend: 'up',   icon: Users,       danger: false },
  { title: 'Reopened',             value: '9',      change: '+1',   trend: 'up',   icon: RotateCcw,   danger: true },
];

const mockPriorityQueue = [
  { id: 'CC-1042', title: 'Major pothole near school — recurring', severity: 'CRITICAL', ward: 'W12', age: '5d', dept: 'Roads' },
  { id: 'CC-1038', title: 'Raw sewage overflow, residential block', severity: 'HIGH',     ward: 'W18', age: '3d', dept: 'Sanitation' },
  { id: 'CC-1031', title: 'Street lighting failure — 200m stretch',severity: 'HIGH',     ward: 'W7',  age: '6d', dept: 'Electrical' },
  { id: 'CC-1027', title: 'Water supply disruption — 300 households', severity: 'CRITICAL', ward: 'W3', age: '2d', dept: 'Water' },
  { id: 'CC-1019', title: 'Garbage accumulation — market area',    severity: 'MEDIUM',   ward: 'W9',  age: '4d', dept: 'Sanitation' },
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

// ─── Severity badge ───────────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    CRITICAL: 'bg-red-50 text-red-700 border border-red-100',
    HIGH:     'bg-orange-50 text-orange-700 border border-orange-100',
    MEDIUM:   'bg-amber-50 text-amber-700 border border-amber-100',
    LOW:      'bg-emerald-50 text-emerald-700 border border-emerald-100',
  };
  return (
    <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${cls[severity] ?? 'bg-gray-100 text-gray-700'}`}>
      {severity}
    </span>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

const Dashboard: React.FC = () => {
  const { data: overview, isLoading, isError } = useAnalyticsOverview();

  return (
    <div className="p-6 min-h-screen space-y-6">

      {/* ── KPI strip ─────────────────────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-xl font-extrabold text-gray-900 tracking-tight">Operations Overview</h2>
            <p className="text-xs text-gray-400 mt-0.5">Real-time municipal operations metrics</p>
          </div>
          {isLoading && (
            <div className="flex items-center gap-2 text-xs text-gray-400 bg-gray-50 px-3 py-1.5 rounded-lg">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
            </div>
          )}
        </div>
        {isError && (
          <div className="bg-amber-50 border border-amber-100 text-amber-700 text-sm rounded-xl px-4 py-3 mb-5 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            Live data unavailable — showing cached figures. Backend not yet connected.
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          {mockKpis.map((kpi, i) => {
            const Icon = kpi.icon;
            const isDown = kpi.trend === 'down';
            return (
              <div
                key={i}
                className="civic-card p-5 hover-lift cursor-default group"
                style={{ animationDelay: `${i * 0.05}s` }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 ${
                    kpi.danger
                      ? 'bg-red-50 text-red-500 group-hover:bg-red-100'
                      : 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100'
                  }`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  {isDown
                    ? <ArrowDownRight className="h-4 w-4 text-emerald-500" />
                    : <ArrowUpRight className={`h-4 w-4 ${kpi.danger ? 'text-red-400' : 'text-gray-300'}`} />}
                </div>
                <p className="text-2xl font-extrabold text-gray-900 tracking-tight">{kpi.value}</p>
                <p className="text-xs text-gray-400 mt-1 font-medium">{kpi.title}</p>
                <p className={`text-xs font-semibold mt-1.5 ${kpi.danger && !isDown ? 'text-red-500' : 'text-emerald-600'}`}>
                  {kpi.change} this week
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── AI Situation Summary ──────────────────────────────────────────── */}
      <section className="civic-card p-5 overflow-hidden relative"
               style={{ background: 'linear-gradient(135deg, rgba(16,185,129,0.04) 0%, rgba(5,150,105,0.02) 100%)' }}>
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
               style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)', boxShadow: '0 4px 15px rgba(22,163,74,0.25)' }}>
            <Brain className="h-5 w-5 text-white" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1.5">
              <h3 className="text-sm font-bold text-gray-900">AI Situation Summary</h3>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-md text-[10px] font-semibold border border-emerald-100">
                <Sparkles className="w-3 h-3" /> AI Generated
              </span>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">{aiSituationSummary}</p>
            <p className="mt-2 text-xs text-gray-400 italic">
              Backed by case database — click any linked case to verify.
            </p>
          </div>
        </div>
      </section>

      {/* ── Priority Queue ────────────────────────────────────────────────── */}
      <section className="civic-card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100/60 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-gray-900">Priority Queue</h3>
            <p className="text-xs text-gray-400 mt-0.5">Sorted by deterministic priority score</p>
          </div>
          <span className="text-xs text-emerald-600 font-semibold hover:text-emerald-700 cursor-pointer transition-colors">
            View All →
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-50">
                <th className="px-5 py-3 text-left text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Case</th>
                <th className="px-5 py-3 text-left text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Title</th>
                <th className="px-5 py-3 text-left text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Severity</th>
                <th className="px-5 py-3 text-left text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Ward</th>
                <th className="px-5 py-3 text-left text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Dept.</th>
                <th className="px-5 py-3 text-left text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Age</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50/80">
              {mockPriorityQueue.map((item) => (
                <tr key={item.id} className="hover:bg-emerald-50/30 transition-colors duration-200 cursor-pointer group">
                  <td className="px-5 py-3.5 font-mono text-xs text-emerald-700 font-semibold">{item.id}</td>
                  <td className="px-5 py-3.5 text-gray-700 max-w-xs truncate group-hover:text-gray-900 transition-colors">{item.title}</td>
                  <td className="px-5 py-3.5"><SeverityBadge severity={item.severity} /></td>
                  <td className="px-5 py-3.5 text-gray-500 font-medium">{item.ward}</td>
                  <td className="px-5 py-3.5 text-gray-500">{item.dept}</td>
                  <td className="px-5 py-3.5 text-gray-400 font-medium">{item.age}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── City Map ──────────────────────────────────────────────────────── */}
      <CityMap />

      {/* ── Heatmap + Dept Performance ───────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2"><WardHeatmap /></div>
        <div className="col-span-1"><DepartmentPerformance /></div>
      </div>

      {/* ── Recent Issues Table ───────────────────────────────────────────── */}
      <RecentIssuesTable />

      {/* ── Analytics Charts ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-6">
        <div className="civic-card p-6">
          <h3 className="text-sm font-bold text-gray-900 mb-1 flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center">
              <TrendingUp className="h-4 w-4 text-emerald-600" />
            </div>
            Resolution Trends
          </h3>
          <p className="text-xs text-gray-400 mb-4">Monthly resolved vs pending cases</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f0" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 12, fill: '#9ca3af' }} />
              <Tooltip
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid #e5e7eb',
                  boxShadow: '0 10px 30px rgba(0,0,0,0.08)',
                  padding: '10px 14px',
                }}
              />
              <Line type="monotone" dataKey="resolved" stroke="#16a34a" strokeWidth={2.5} dot={false} name="Resolved" />
              <Line type="monotone" dataKey="pending"  stroke="#ef4444" strokeWidth={2.5} dot={false} name="Pending" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="civic-card p-6">
          <h3 className="text-sm font-bold text-gray-900 mb-1 flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center">
              <MapPin className="h-4 w-4 text-emerald-600" />
            </div>
            Top Issue Categories
          </h3>
          <p className="text-xs text-gray-400 mb-4">Distribution by category type</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f0" />
              <XAxis type="number" tick={{ fontSize: 12, fill: '#9ca3af' }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 12, fill: '#6b7280' }} width={70} />
              <Tooltip
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid #e5e7eb',
                  boxShadow: '0 10px 30px rgba(0,0,0,0.08)',
                  padding: '10px 14px',
                }}
              />
              <Bar dataKey="value" fill="url(#greenGradient)" radius={[0, 6, 6, 0]} name="Cases" />
              <defs>
                <linearGradient id="greenGradient" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#16a34a" />
                  <stop offset="100%" stopColor="#22c55e" />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
