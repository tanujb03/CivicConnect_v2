/**
 * O04 — Analytics (Overlooker)
 * Read-only analytics dashboard with trend charts and category breakdown.
 * Same data as A10 but read-only with no drill-down actions.
 */
import React from 'react';
import { TrendingUp, BarChart3, Brain } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line,
} from 'recharts';

const trendData = [
  { week: 'W1', created: 45, resolved: 38 },
  { week: 'W2', created: 52, resolved: 44 },
  { week: 'W3', created: 48, resolved: 51 },
  { week: 'W4', created: 61, resolved: 42 },
];

const categoryData = [
  { name: 'Roads', value: 145 },
  { name: 'Lighting', value: 89 },
  { name: 'Garbage', value: 76 },
  { name: 'Water', value: 54 },
  { name: 'Drainage', value: 43 },
];

const deptSla = [
  { dept: 'Roads', sla: 82, active: 23 },
  { dept: 'Electrical', sla: 74, active: 18 },
  { dept: 'Sanitation', sla: 91, active: 12 },
  { dept: 'Water', sla: 78, active: 20 },
  { dept: 'Garbage', sla: 88, active: 15 },
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload) return null;
  return (
    <div className="cc-card p-3 text-xs" style={{ boxShadow: 'var(--shadow-hard)' }}>
      <p className="font-mono font-semibold text-ink mb-1">{label}</p>
      {payload.map((e: any, i: number) => (
        <p key={i} style={{ color: e.color }} className="font-medium">{e.name}: {e.value}</p>
      ))}
    </div>
  );
};

const AnalyticsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">O04</div>
        <h1 className="cc-title cc-headline-pop">Analytics</h1>
        <p className="text-xs font-mono text-muted mt-1">Read-only city analytics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trend Chart */}
        <div className="cc-card p-6 cc-card-lift cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
              <TrendingUp className="h-3.5 w-3.5 text-ink" />
            </div>
            <h3 className="text-sm font-display text-ink">Case Trend</h3>
          </div>
          <p className="text-xs font-mono text-muted mb-4">Created vs resolved per week</p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--dot)" />
              <XAxis dataKey="week" tick={{ fontSize: 11, fill: 'var(--muted)', fontFamily: 'var(--font-mono)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--muted)', fontFamily: 'var(--font-mono)' }} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="created" stroke="var(--fire)" strokeWidth={2} dot={false} name="Created" />
              <Line type="monotone" dataKey="resolved" stroke="var(--lime)" strokeWidth={2} dot={false} name="Resolved" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Category breakdown */}
        <div className="cc-card p-6 cc-card-lift cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
              <BarChart3 className="h-3.5 w-3.5 text-ink" />
            </div>
            <h3 className="text-sm font-display text-ink">Category Mix</h3>
          </div>
          <p className="text-xs font-mono text-muted mb-4">Distribution by type</p>
          <ResponsiveContainer width="100%" height={200}>
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

      {/* Department SLA */}
      <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
        <h3 className="font-display text-sm text-ink mb-4">Department SLA Compliance</h3>
        <div className="space-y-3">
          {deptSla.map((d, i) => (
            <div key={d.dept} className="cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-ink">{d.dept}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-muted">{d.active} active</span>
                  <span className={`cc-chip text-[9px] py-0 px-1.5 ${d.sla >= 85 ? 'bg-lime text-ink' : d.sla >= 70 ? 'bg-amber text-ink' : 'bg-fire text-on-fire'}`}>
                    {d.sla}%
                  </span>
                </div>
              </div>
              <div className="cc-meter">
                <div
                  className={`cc-meter-fill cc-bar-grow-x ${d.sla >= 70 ? 'cc-meter-fill-lime' : 'cc-meter-fill-risk'}`}
                  style={{ width: `${d.sla}%`, '--stagger-index': i } as React.CSSProperties}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AnalyticsPage;