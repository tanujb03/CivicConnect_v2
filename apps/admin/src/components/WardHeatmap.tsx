/**
 * WardHeatmap — dashboard widget showing ward heat tiles.
 * Heat steps 1 to 5 use lightness-ordered colors so the scale reads without colour.
 */
import React from 'react';

const wardsData = [
  { id: 'W01', label: 'Ward 01', cases: 8,  step: 1 },
  { id: 'W02', label: 'Ward 02', cases: 14, step: 2 },
  { id: 'W03', label: 'Ward 03', cases: 27, step: 3 },
  { id: 'W04', label: 'Ward 04', cases: 5,  step: 1 },
  { id: 'W05', label: 'Ward 05', cases: 11, step: 2 },
  { id: 'W06', label: 'Ward 06', cases: 19, step: 3 },
  { id: 'W07', label: 'Ward 07', cases: 34, step: 4 },
  { id: 'W08', label: 'Ward 08', cases: 3,  step: 1 },
  { id: 'W09', label: 'Ward 09', cases: 22, step: 3 },
  { id: 'W10', label: 'Ward 10', cases: 6,  step: 1 },
  { id: 'W11', label: 'Ward 11', cases: 15, step: 2 },
  { id: 'W12', label: 'Ward 12', cases: 45, step: 5 },
  { id: 'W13', label: 'Ward 13', cases: 9,  step: 1 },
  { id: 'W14', label: 'Ward 14', cases: 12, step: 2 },
  { id: 'W15', label: 'Ward 15', cases: 7,  step: 1 },
  { id: 'W16', label: 'Ward 16', cases: 20, step: 3 },
  { id: 'W17', label: 'Ward 17', cases: 16, step: 2 },
  { id: 'W18', label: 'Ward 18', cases: 38, step: 4 },
];

function getHeatColor(step: number): string {
  const colors: Record<number, string> = {
    1: 'var(--heat-1)',
    2: 'var(--heat-2)',
    3: 'var(--heat-3)',
    4: 'var(--heat-4)',
    5: 'var(--heat-5)',
  };
  return colors[step] ?? 'var(--dot)';
}

function getTextColor(step: number): string {
  return step >= 4 ? 'var(--on-wine)' : 'var(--ink)';
}

const WardHeatmap: React.FC = () => {
  return (
    <div className="cc-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display text-sm text-ink">Ward Heatmap</h3>
          <p className="text-xs font-mono text-muted mt-0.5">Active cases by ward</p>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map(step => (
            <div
              key={step}
              className="w-5 h-5 rounded border border-ink/30"
              style={{ background: getHeatColor(step) }}
              title={`Heat step ${step}`}
            />
          ))}
          <span className="text-[10px] font-mono text-muted ml-1">Low → High</span>
        </div>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
        {wardsData.map((ward, i) => (
          <div
            key={ward.id}
            className="cc-heat-tile cc-card-lift cc-fade-up cursor-pointer"
            style={{
              background: getHeatColor(ward.step),
              color: getTextColor(ward.step),
              '--stagger-index': i,
            } as React.CSSProperties}
          >
            <div className="font-mono text-[10px] opacity-70">{ward.id}</div>
            <div className="font-display text-lg">{ward.cases}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WardHeatmap;