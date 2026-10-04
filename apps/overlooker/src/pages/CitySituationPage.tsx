/**
 * O02 — City Situation
 * Read-only city view with ward heat tiles, hotspot list, and AI diagnostic.
 * No mutations. Data: /analytics/wards, /analytics/hotspots, POST /analytics/explain.
 */
import React, { useState } from 'react';
import { Brain, MapPin, AlertTriangle, Layers } from 'lucide-react';

const wardsData = [
  { id: 'W01', cases: 8, step: 1 }, { id: 'W02', cases: 14, step: 2 },
  { id: 'W03', cases: 27, step: 3 }, { id: 'W04', cases: 5, step: 1 },
  { id: 'W05', cases: 11, step: 2 }, { id: 'W06', cases: 19, step: 3 },
  { id: 'W07', cases: 34, step: 4 }, { id: 'W08', cases: 3, step: 1 },
  { id: 'W09', cases: 22, step: 3 }, { id: 'W10', cases: 6, step: 1 },
  { id: 'W11', cases: 15, step: 2 }, { id: 'W12', cases: 45, step: 5 },
  { id: 'W13', cases: 9, step: 1 }, { id: 'W14', cases: 12, step: 2 },
  { id: 'W15', cases: 7, step: 1 }, { id: 'W16', cases: 20, step: 3 },
  { id: 'W17', cases: 16, step: 2 }, { id: 'W18', cases: 38, step: 4 },
];

const hotspots = [
  { location: 'MG Road corridor, W12', cases: 31, radius: '800m', category: 'Roads' },
  { location: 'Market area, W18', cases: 22, radius: '600m', category: 'Sanitation' },
  { location: 'Station Road, W3', cases: 18, radius: '400m', category: 'Water' },
];

const aiDiagnostic =
  'Road cases in W12 are concentrated within 800m of the school junction. The recurring pattern suggests infrastructure degradation rather than isolated incidents. Sanitation backlog in W18 is 27% above the 30-day baseline and rising.';

const CitySituationPage: React.FC = () => {
  const [selectedWard, setSelectedWard] = useState<string | null>(null);
  const ward = wardsData.find(w => w.id === selectedWard);

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">O02</div>
        <h1 className="cc-title cc-headline-pop">City Situation</h1>
        <p className="text-xs font-mono text-muted mt-1">Read-only view of city operations</p>
      </div>

      {/* AI Diagnostic */}
      <div className="cc-ai-panel cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-md border-2 border-on-wine/30 flex items-center justify-center shrink-0"
            style={{ background: 'var(--rust-deep)' }}>
            <Brain className="h-4 w-4 text-on-wine" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-sm font-display text-on-wine">AI City Diagnostic</h3>
              <span className="cc-chip cc-chip-dashed text-[10px] border-on-wine/40 text-on-wine/80">AI Generated</span>
            </div>
            <p className="text-sm text-on-wine/80 leading-relaxed">{aiDiagnostic}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ward Heatmap */}
        <div className="lg:col-span-2">
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-sm text-ink flex items-center gap-2">
                <Layers className="h-4 w-4" style={{ color: 'var(--wine)' }} />
                Ward Heatmap
              </h3>
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map(s => (
                  <div key={s} className="w-4 h-4 rounded border border-ink/30" style={{ background: `var(--heat-${s})` }} />
                ))}
                <span className="text-[10px] font-mono text-muted ml-1">Low → High</span>
              </div>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
              {wardsData.map((w, i) => (
                <button
                  key={w.id}
                  onClick={() => setSelectedWard(w.id)}
                  className={`cc-heat-tile cc-card-lift cc-fade-up ${selectedWard === w.id ? 'ring-3 ring-lime' : ''}`}
                  style={{
                    background: `var(--heat-${w.step})`,
                    color: w.step >= 4 ? 'var(--on-wine)' : 'var(--ink)',
                    '--stagger-index': i,
                  } as React.CSSProperties}
                >
                  <div className="font-mono text-[10px] opacity-70">{w.id}</div>
                  <div className="font-display text-lg">{w.cases}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Ward Detail */}
        <div className="lg:col-span-1">
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
            <h3 className="font-display text-sm text-ink mb-4">
              {ward ? `${ward.id} Detail` : 'Select a ward'}
            </h3>
            {ward ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-dot">
                  <span className="text-[10px] font-mono text-muted uppercase">Cases</span>
                  <span className="text-sm font-semibold text-ink">{ward.cases}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-dot">
                  <span className="text-[10px] font-mono text-muted uppercase">Heat Level</span>
                  <div className="w-6 h-6 rounded border border-ink/30" style={{ background: `var(--heat-${ward.step})` }} />
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted font-mono py-8 text-center">Click a tile to see details</p>
            )}
          </div>
        </div>
      </div>

      {/* Hotspots */}
      <div className="cc-fade-up" style={{ '--stagger-index': 3 } as React.CSSProperties}>
        <h2 className="font-display text-lg text-ink mb-3 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" style={{ color: 'var(--fire)' }} />
          Active Hotspots
        </h2>
        <div className="space-y-3">
          {hotspots.map((hs, i) => (
            <div key={i} className="cc-card p-4 cc-card-lift cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-ink">{hs.location}</p>
                  <p className="text-xs font-mono text-muted mt-1">{hs.category} · {hs.cases} cases · {hs.radius} radius</p>
                </div>
                <span className="cc-chip text-[10px] bg-fire text-on-fire">{hs.cases}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CitySituationPage;
