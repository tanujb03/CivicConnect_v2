/**
 * A10 — Analytics
 * Three stacked folder-tab cards: Descriptive (white), Diagnostic (wine), Patterns (fire).
 *
 * Data: /analytics/overview (trend, categories), /wards, /hotspots,
 *       /recurrence, POST /analytics/explain.
 */
import React, { useState } from 'react';
import { BarChart3, Brain, AlertTriangle, TrendingUp, MapPin } from 'lucide-react';
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

const categoryMix = [
  { name: 'Roads', value: 145 },
  { name: 'Lighting', value: 89 },
  { name: 'Garbage', value: 76 },
  { name: 'Water', value: 54 },
  { name: 'Drainage', value: 43 },
];

const hotspots = [
  { location: 'MG Road corridor, W12', cases: 31, baseline: 12, radius: '800m' },
  { location: 'Market area, W18', cases: 22, baseline: 8, radius: '600m' },
  { location: 'Station Road, W3', cases: 18, baseline: 10, radius: '400m' },
];

const recurrence = [
  { location: 'School junction, W12', count: 6, category: 'Pothole', lastSeen: '2d ago' },
  { location: 'Temple Road, W7', count: 4, category: 'Lighting', lastSeen: '5d ago' },
  { location: 'Block B drain, W18', count: 3, category: 'Drainage', lastSeen: '3d ago' },
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

type Tab = 'descriptive' | 'diagnostic' | 'patterns';

const AnalyticsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('descriptive');

  const tabs: { id: Tab; label: string; tone: string }[] = [
    { id: 'descriptive', label: 'Descriptive', tone: '' },
    { id: 'diagnostic', label: 'Diagnostic', tone: 'cc-folder-tab-wine' },
    { id: 'patterns', label: 'Patterns', tone: 'cc-folder-tab-fire' },
  ];

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A10</div>
        <h1 className="cc-title cc-headline-pop">Analytics</h1>
      </div>

      {/* Folder tabs */}
      <div className="cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <div className="cc-folder-tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`cc-folder-tab ${activeTab === tab.id ? 'cc-folder-tab-active' : ''} ${activeTab === tab.id && tab.tone ? tab.tone : ''}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="cc-card" style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0, borderTop: 'none' }}>
          <div className="p-6">
            {activeTab === 'descriptive' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Trend chart */}
                  <div>
                    <h4 className="font-display text-sm text-ink mb-1 flex items-center gap-2">
                      <TrendingUp className="h-4 w-4" style={{ color: 'var(--wine)' }} />
                      30-Day Trend
                    </h4>
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

                  {/* Category mix */}
                  <div>
                    <h4 className="font-display text-sm text-ink mb-1 flex items-center gap-2">
                      <BarChart3 className="h-4 w-4" style={{ color: 'var(--wine)' }} />
                      Category Mix
                    </h4>
                    <p className="text-xs font-mono text-muted mb-4">Distribution by type</p>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={categoryMix} layout="vertical">
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
            )}

            {activeTab === 'diagnostic' && (
              <div className="space-y-5">
                <div className="cc-ai-panel">
                  <div className="flex items-center gap-2 mb-3">
                    <Brain className="h-4 w-4" />
                    <h4 className="font-display text-sm text-on-wine">AI Diagnostic Summary</h4>
                    <span className="cc-chip cc-chip-dashed text-[10px] border-on-wine/40 text-on-wine/80">AI Generated</span>
                  </div>
                  <p className="text-sm text-on-wine/80 leading-relaxed">
                    Road-related cases are concentrated in W12 and W18 (31 in 7 days, 19 within 800m). 
                    Sanitation backlog in W18 is 27% above baseline. Three locations have recurring reports 
                    suggesting systemic infrastructure issues rather than isolated incidents.
                  </p>
                </div>

                <h4 className="font-display text-sm text-ink flex items-center gap-2">
                  <MapPin className="h-4 w-4" style={{ color: 'var(--fire)' }} />
                  Active Hotspots
                </h4>
                <div className="space-y-2">
                  {hotspots.map((hs, i) => (
                    <div key={i} className="cc-card p-4 cc-card-lift cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-ink">{hs.location}</p>
                          <p className="text-xs font-mono text-muted mt-1">
                            {hs.cases} cases (baseline: {hs.baseline}) · {hs.radius} radius
                          </p>
                        </div>
                        <span className="cc-chip text-[10px] bg-fire text-on-fire">{hs.cases} cases</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'patterns' && (
              <div className="space-y-5">
                <h4 className="font-display text-sm text-ink flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" style={{ color: 'var(--fire)' }} />
                  Recurring Problems
                </h4>
                <div className="space-y-2">
                  {recurrence.map((r, i) => (
                    <div key={i} className="cc-card-fire p-4 cc-card-lift cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold">{r.location}</p>
                          <p className="text-xs opacity-80 mt-1">
                            {r.category} · {r.count} recurrences · Last: {r.lastSeen}
                          </p>
                        </div>
                        <span className="cc-chip text-[10px] border-on-fire/40 text-on-fire">{r.count}x</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsPage;
