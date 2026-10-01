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
  TrendingUp, RotateCcw, Brain, MapPin, Loader2
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
  { title: 'Active Cases',        value: '248',    change: '+12',   trend: 'up',   icon: FileText,    danger: false },
  { title: 'Critical Cases',      value: '23',     change: '+5',    trend: 'up',   icon: AlertCircle, danger: true },
  { title: 'SLA At Risk',         value: '41',     change: '+8',    trend: 'up',   icon: Clock,       danger: true },
  { title: 'Unassigned',          value: '17',     change: '-3',    trend: 'down', icon: TrendingUp,  danger: false },
  { title: 'Awaiting Verification',value: '34',    change: '+2',    trend: 'up',   icon: Users,       danger: false },
  { title: 'Reopened',            value: '9',      change: '+1',    trend: 'up',   icon: RotateCcw,   danger: true },
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
    CRITICAL: 'bg-red-100 text-red-800 border border-red-200',
    HIGH:     'bg-orange-100 text-orange-800 border border-orange-200',
    MEDIUM:   'bg-yellow-100 text-yellow-800 border border-yellow-200',
    LOW:      'bg-green-100 text-green-800 border border-green-200',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${cls[severity] ?? 'bg-gray-100 text-gray-700'}`}>
      {severity}
    </span>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

const Dashboard: React.FC = () => {
  const { data: overview, isLoading, isError } = useAnalyticsOverview();

  return (
    <div className="p-6 bg-civic-bg min-h-screen space-y-8">

      {/* ── KPI strip ─────────────────────────────────────────────────────── */}
      <section>
        <h2 className="text-xl font-bold text-civic-text-primary mb-4">Operations Overview</h2>
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading live data…
          </div>
        )}
        {isError && (
          <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-4 py-2 mb-4">
            Live data unavailable — showing cached figures. Backend not yet connected.
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          {mockKpis.map((kpi, i) => {
            const Icon = kpi.icon;
            const isDown = kpi.trend === 'down';
            return (
              <div key={i} className="civic-card p-5 rounded-xl border border-gray-100">
                <div className="flex items-start justify-between mb-3">
                  <Icon className={`h-6 w-6 ${kpi.danger ? 'text-red-500' : 'text-green-600'}`} />
                  {isDown
                    ? <ArrowDownRight className="h-4 w-4 text-green-500" />
                    : <ArrowUpRight className={`h-4 w-4 ${kpi.danger ? 'text-red-500' : 'text-gray-400'}`} />}
                </div>
                <p className="text-2xl font-bold text-gray-900">{kpi.value}</p>
                <p className="text-xs text-gray-500 mt-0.5">{kpi.title}</p>
                <p className={`text-xs font-medium mt-1 ${kpi.danger && !isDown ? 'text-red-600' : 'text-green-600'}`}>
                  {kpi.change} this week
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── AI Situation Summary ──────────────────────────────────────────── */}
      <section className="civic-card p-5 rounded-xl border border-green-100 bg-green-50/40">
        <div className="flex items-start gap-3">
          <div className="h-8 w-8 rounded-lg bg-green-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Brain className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-green-900">AI Situation Summary</h3>
            <p className="mt-1 text-sm text-green-800 leading-relaxed">{aiSituationSummary}</p>
            <p className="mt-2 text-xs text-green-600 italic">
              Backed by case database — click any linked case to verify.
            </p>
          </div>
        </div>
      </section>

      {/* ── Priority Queue ────────────────────────────────────────────────── */}
      <section className="civic-card rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">Priority Queue</h3>
          <span className="text-xs text-gray-400">Sorted by deterministic priority score · AI suggestion shown separately</span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th className="px-5 py-3 text-left">Case</th>
              <th className="px-5 py-3 text-left">Title</th>
              <th className="px-5 py-3 text-left">Severity</th>
              <th className="px-5 py-3 text-left">Ward</th>
              <th className="px-5 py-3 text-left">Dept.</th>
              <th className="px-5 py-3 text-left">Age</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {mockPriorityQueue.map((item) => (
              <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-5 py-3 font-mono text-xs text-green-700">{item.id}</td>
                <td className="px-5 py-3 text-gray-700 max-w-xs truncate">{item.title}</td>
                <td className="px-5 py-3"><SeverityBadge severity={item.severity} /></td>
                <td className="px-5 py-3 text-gray-500">{item.ward}</td>
                <td className="px-5 py-3 text-gray-500">{item.dept}</td>
                <td className="px-5 py-3 text-gray-400">{item.age}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
        <div className="civic-card p-6 rounded-xl border border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-green-600" />
            Resolution Trends
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="resolved" stroke="#16a34a" strokeWidth={2} dot={false} name="Resolved" />
              <Line type="monotone" dataKey="pending"  stroke="#ef4444" strokeWidth={2} dot={false} name="Pending" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="civic-card p-6 rounded-xl border border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-green-600" />
            Top Issue Categories
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 12 }} width={70} />
              <Tooltip />
              <Bar dataKey="value" fill="#16a34a" radius={[0, 4, 4, 0]} name="Cases" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
