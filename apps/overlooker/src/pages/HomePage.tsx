/**
 * O01 — Overlooker Home
 * Wine hero with scalloped edge, city pulse KPI strip, live feed of
 * recent updates, quick-look map, AI-generated city summary.
 *
 * Data: /analytics/overview, /cases?limit=5&sort=-created_at
 * Read-only — no mutations.
 */
import React from 'react';
import {
  MapPin, AlertTriangle, Clock, BarChart3, TrendingUp,
  Users, Bell, ChevronRight, Brain,
} from 'lucide-react';
import CivicLeafletMap from '../components/common/CivicLeafletMap';

// Mock city pulse data
const cityPulse = [
  { label: 'Active Cases', value: 248, trend: '+12', up: true },
  { label: 'Resolved Today', value: 34, trend: '+8', up: true },
  { label: 'SLA Compliance', value: '82%', trend: '-3%', up: false },
  { label: 'Citizen Reports', value: 1240, trend: '+45', up: true },
];

const mockUpdates = [
  { id: '1', title: 'Major pothole repair completed — MG Road, W12', time: '2h ago', type: 'resolved' },
  { id: '2', title: '50 citizens reported water logging in W3', time: '3h ago', type: 'alert' },
  { id: '3', title: 'Traffic light outage at Central Crossing', time: '4h ago', type: 'alert' },
  { id: '4', title: 'Water main repair completed in W12', time: '6h ago', type: 'resolved' },
  { id: '5', title: '89% issue resolution rate this week (+5%)', time: '1d ago', type: 'info' },
  { id: '6', title: 'Tree plantation drive scheduled this weekend', time: '1d ago', type: 'info' },
  { id: '7', title: 'Road maintenance on Park Avenue, expect delays', time: '12h ago', type: 'alert' },
  { id: '8', title: 'Citizen satisfaction index rises by 12%', time: '3d ago', type: 'info' },
];

const aiCitySummary =
  'City operations are running at 82% SLA compliance. Road-related cases in W12 and W18 remain elevated but trending down after crew dispatch yesterday. Sanitation backlog in W18 is 27% above the 30-day baseline. No city-wide emergencies active.';

function TypeBadge({ type }: { type: string }) {
  const cls: Record<string, string> = {
    resolved: 'bg-lime text-ink',
    alert: 'bg-fire text-on-fire',
    info: 'bg-lime-tint text-ink',
  };
  return (
    <span className={`cc-chip text-[9px] py-0 px-1.5 ${cls[type] ?? ''}`}>
      {type}
    </span>
  );
}

const HomePage: React.FC = () => {
  return (
    <div className="space-y-8 -mt-10">
      {/* ── Wine Hero Band with scalloped edge ────────────────────────── */}
      <div className="overlooker-hero">
        <div className="max-w-4xl">
          <p className="text-on-wine/50 font-mono text-xs uppercase tracking-widest mb-2 cc-fade-up">
            O01 — City Overview
          </p>
          <h1 className="font-display text-3xl md:text-4xl text-on-wine cc-headline-pop">
            Good morning, Overlooker
          </h1>
          <p className="text-on-wine/60 mt-3 text-sm max-w-lg cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
            Here is the pulse of your city. All data is read-only and refreshes every 5 minutes.
          </p>
        </div>
      </div>

      {/* Push content below scalloped edge */}
      <div style={{ height: '12px' }} />

      {/* ── City Pulse KPI Strip ──────────────────────────────────────── */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cityPulse.map((kpi, i) => (
          <div
            key={kpi.label}
            className="cc-kpi-card cc-card-lift cc-fade-up"
            style={{ '--stagger-index': i } as React.CSSProperties}
          >
            <p className="cc-kpi-value">{kpi.value}</p>
            <p className="cc-kpi-label">{kpi.label}</p>
            <p className={`text-xs font-mono font-semibold mt-1 ${kpi.up ? 'text-lime' : 'text-fire'}`}>
              {kpi.trend}
            </p>
          </div>
        ))}
      </section>

      {/* ── AI City Summary (wine panel) ─────────────────────────────── */}
      <section className="cc-ai-panel cc-fade-up" style={{ '--stagger-index': 4 } as React.CSSProperties}>
        <div className="flex items-start gap-4">
          <div className="relative shrink-0">
            <div
              className="w-10 h-10 rounded-md border-2 border-on-wine/30 flex items-center justify-center"
              style={{ background: 'var(--rust-deep)' }}
            >
              <Brain className="h-5 w-5 text-on-wine" />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-sm font-display text-on-wine">City AI Summary</h3>
              <span className="cc-chip cc-chip-dashed text-[10px] border-on-wine/40 text-on-wine/80">
                AI Generated
              </span>
            </div>
            <div className="space-y-1">
              {aiCitySummary.split('. ').map((sentence, i) => (
                <p
                  key={i}
                  className="cc-typed-line text-sm text-on-wine/80 leading-relaxed"
                  style={{ '--line-index': i } as React.CSSProperties}
                >
                  {sentence}{i < aiCitySummary.split('. ').length - 1 ? '.' : ''}
                </p>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Live Feed ────────────────────────────────────────────────── */}
      <section className="cc-fade-up" style={{ '--stagger-index': 5 } as React.CSSProperties}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-display text-lg text-ink">Live Feed</h2>
            <p className="text-xs font-mono text-muted mt-0.5">Recent city updates</p>
          </div>
          <span className="cc-chip text-[9px] py-0 px-1.5 font-mono">{mockUpdates.length} updates</span>
        </div>

        <div className="space-y-3">
          {mockUpdates.map((update, i) => (
            <div
              key={update.id}
              className="cc-card p-4 cc-card-lift cc-fade-up cursor-pointer group"
              style={{ '--stagger-index': i } as React.CSSProperties}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-ink font-medium group-hover:text-wine transition-colors">
                    {update.title}
                  </p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <TypeBadge type={update.type} />
                    <span className="text-[10px] font-mono text-muted">{update.time}</span>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-muted shrink-0 group-hover:text-ink transition-colors" />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Quick Map ────────────────────────────────────────────────── */}
      <section className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 6 } as React.CSSProperties}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4" style={{ color: 'var(--wine)' }} />
            <h3 className="font-display text-sm text-ink">City Map</h3>
          </div>
          <span className="cc-chip text-[9px] py-0 px-1.5 font-mono bg-lime-tint">Live</span>
        </div>
        <CivicLeafletMap height="300px" compact={true} />
        <p className="text-[10px] font-mono text-muted mt-2">
          Read-only view — overlays show active cases and heat zones.
        </p>
      </section>
    </div>
  );
};

export default HomePage;