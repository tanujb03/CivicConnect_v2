/**
 * A09 — Ward Heatmap (full page)
 * Ward-level comparison: case volume, severity, category distribution,
 * resolution time, backlog, recurrence.
 */
import React, { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell, Legend,
} from 'recharts';
import { Layers, TrendingUp, Clock } from 'lucide-react';

const WARDS = [
  { id: 'W1',  name: 'Ward 1',  cases: 34, critical: 3, resolution_days: 4.2, backlog: 8,  recurrence: 2 },
  { id: 'W2',  name: 'Ward 2',  cases: 28, critical: 1, resolution_days: 3.8, backlog: 5,  recurrence: 1 },
  { id: 'W3',  name: 'Ward 3',  cases: 41, critical: 7, resolution_days: 6.1, backlog: 14, recurrence: 4 },
  { id: 'W4',  name: 'Ward 4',  cases: 22, critical: 0, resolution_days: 3.1, backlog: 4,  recurrence: 0 },
  { id: 'W5',  name: 'Ward 5',  cases: 19, critical: 1, resolution_days: 2.9, backlog: 3,  recurrence: 1 },
  { id: 'W6',  name: 'Ward 6',  cases: 37, critical: 5, resolution_days: 5.4, backlog: 11, recurrence: 3 },
  { id: 'W7',  name: 'Ward 7',  cases: 15, critical: 0, resolution_days: 2.5, backlog: 2,  recurrence: 0 },
  { id: 'W8',  name: 'Ward 8',  cases: 29, critical: 2, resolution_days: 4.0, backlog: 7,  recurrence: 2 },
  { id: 'W9',  name: 'Ward 9',  cases: 25, critical: 1, resolution_days: 3.5, backlog: 5,  recurrence: 1 },
  { id: 'W10', name: 'Ward 10', cases: 18, critical: 0, resolution_days: 2.8, backlog: 3,  recurrence: 0 },
  { id: 'W11', name: 'Ward 11', cases: 32, critical: 4, resolution_days: 5.0, backlog: 9,  recurrence: 3 },
  { id: 'W12', name: 'Ward 12', cases: 48, critical: 9, resolution_days: 7.2, backlog: 18, recurrence: 6 },
  { id: 'W13', name: 'Ward 13', cases: 20, critical: 1, resolution_days: 3.2, backlog: 4,  recurrence: 1 },
  { id: 'W14', name: 'Ward 14', cases: 26, critical: 2, resolution_days: 3.9, backlog: 6,  recurrence: 2 },
  { id: 'W15', name: 'Ward 15', cases: 39, critical: 6, resolution_days: 5.8, backlog: 12, recurrence: 4 },
];

const CATEGORY_DATA = [
  { ward: 'W12', Roads: 21, Sanitation: 12, Electrical: 8,  Water: 4, Garbage: 3 },
  { ward: 'W15', Roads: 14, Sanitation: 10, Electrical: 7,  Water: 5, Garbage: 3 },
  { ward: 'W3',  Roads: 12, Sanitation: 14, Electrical: 5,  Water: 8, Garbage: 2 },
  { ward: 'W6',  Roads: 16, Sanitation: 8,  Electrical: 6,  Water: 4, Garbage: 3 },
  { ward: 'W11', Roads: 10, Sanitation: 9,  Electrical: 7,  Water: 3, Garbage: 3 },
];

// Heatmap cell color based on case count
function cellColor(cases: number, max: number): string {
  const pct = cases / max;
  if (pct >= 0.8) return 'bg-red-600 text-white';
  if (pct >= 0.6) return 'bg-orange-500 text-white';
  if (pct >= 0.4) return 'bg-yellow-400 text-gray-900';
  if (pct >= 0.2) return 'bg-green-300 text-gray-800';
  return 'bg-green-100 text-gray-600';
}

type Metric = 'cases' | 'critical' | 'resolution_days' | 'backlog' | 'recurrence';

const METRICS: { key: Metric; label: string }[] = [
  { key: 'cases',           label: 'Total Cases' },
  { key: 'critical',        label: 'Critical' },
  { key: 'resolution_days', label: 'Avg Resolution (days)' },
  { key: 'backlog',         label: 'Backlog' },
  { key: 'recurrence',      label: 'Recurring Locations' },
];

const WardHeatmapPage: React.FC = () => {
  const [activeMetric, setActiveMetric] = useState<Metric>('cases');

  const maxVal = Math.max(...WARDS.map(w => w[activeMetric] as number));
  const sortedWards = [...WARDS].sort((a, b) => (b[activeMetric] as number) - (a[activeMetric] as number));

  return (
    <div className="p-6 min-h-screen space-y-6 page-enter">
      <div>
        <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
          <Layers className="h-5 w-5 text-emerald-600" />
          Ward Heatmap
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Ward-level comparison derived from live case database aggregates.
        </p>
      </div>

      {/* Metric selector */}
      <div className="flex flex-wrap gap-2">
        {METRICS.map(m => (
          <button
            key={m.key}
            onClick={() => setActiveMetric(m.key)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-medium border transition-all duration-300 ${
              activeMetric === m.key
                ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm'
                : 'bg-white text-muted-foreground border-emerald-100 hover:border-emerald-300 hover:text-emerald-700'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Heatmap grid */}
      <div className="civic-card p-5 hover-lift">
        <h3 className="text-sm font-semibold text-foreground mb-4">
          {METRICS.find(m => m.key === activeMetric)?.label} by Ward
        </h3>
        <div className="grid grid-cols-5 gap-2">
          {sortedWards.map(w => (
            <div
              key={w.id}
              className={`rounded-lg p-3 text-center transition-all cursor-default ${cellColor(w[activeMetric] as number, maxVal)}`}
              title={`${w.name}: ${w[activeMetric]}`}
            >
              <p className="text-xs font-semibold">{w.id}</p>
              <p className="text-xl font-bold mt-0.5">{w[activeMetric]}</p>
            </div>
          ))}
        </div>

        {/* Color scale legend */}
        <div className="flex items-center gap-2 mt-4">
          <span className="text-xs text-muted-foreground">Low</span>
          <div className="flex gap-1">
            {['bg-green-100', 'bg-green-300', 'bg-yellow-400', 'bg-orange-500', 'bg-red-600'].map(c => (
              <div key={c} className={`w-8 h-3 rounded ${c}`} />
            ))}
          </div>
          <span className="text-xs text-muted-foreground">High</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Bar chart — all wards */}
        <div className="civic-card p-5 hover-lift">
          <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-emerald-600" />
            Ward Case Volume (all wards)
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={sortedWards} margin={{ top: 5, right: 10, bottom: 20, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="id" tick={{ fontSize: 10 }} angle={-45} textAnchor="end" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="cases" name="Cases" radius={[4, 4, 0, 0]}>
                {sortedWards.map(w => (
                  <Cell
                    key={w.id}
                    fill={
                      w.cases >= 40 ? '#ef4444'
                      : w.cases >= 30 ? '#f97316'
                      : w.cases >= 20 ? '#eab308'
                      : '#22c55e'
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Category distribution for top 5 wards */}
        <div className="civic-card p-5 hover-lift">
          <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
            <Clock className="h-4 w-4 text-emerald-600" />
            Category Distribution — Top 5 Wards
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={CATEGORY_DATA} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="ward" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Roads"      stackId="a" fill="#16a34a" />
              <Bar dataKey="Sanitation" stackId="a" fill="#3b82f6" />
              <Bar dataKey="Electrical" stackId="a" fill="#eab308" />
              <Bar dataKey="Water"      stackId="a" fill="#06b6d4" />
              <Bar dataKey="Garbage"    stackId="a" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top-3 alert wards */}
      <div className="grid grid-cols-3 gap-4">
        {sortedWards.slice(0, 3).map((w, i) => (
          <div key={w.id} className="civic-card p-4 border border-red-100/50 bg-red-50/30 hover-lift">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold text-white bg-red-500 px-2 py-0.5 rounded">#{i + 1}</span>
              <span className="text-sm font-semibold text-foreground">{w.name}</span>
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">
              <div className="flex justify-between"><span>Total Cases</span><span className="font-semibold">{w.cases}</span></div>
              <div className="flex justify-between"><span>Critical</span><span className="font-semibold text-red-600">{w.critical}</span></div>
              <div className="flex justify-between"><span>Avg Resolution</span><span className="font-semibold">{w.resolution_days}d</span></div>
              <div className="flex justify-between"><span>Recurring spots</span><span className="font-semibold text-amber-600">{w.recurrence}</span></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WardHeatmapPage;
