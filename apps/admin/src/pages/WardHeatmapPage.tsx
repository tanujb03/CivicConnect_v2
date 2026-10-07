/**
 * A09 — Ward Heatmap Page
 * Metric selector, schematic tiles coloured by heat step,
 * ward detail panel, full ward table.
 *
 * Data: /analytics/wards. Tiles are schematic until the API returns ward geometry.
 */
import React, { useState } from 'react';
import { Layers, ArrowUpDown } from 'lucide-react';

const wardsData = [
  { id: 'W01', cases: 8, resolved: 6, sla: 88, backlog: 2, step: 1 },
  { id: 'W02', cases: 14, resolved: 10, sla: 82, backlog: 4, step: 2 },
  { id: 'W03', cases: 27, resolved: 18, sla: 71, backlog: 9, step: 3 },
  { id: 'W04', cases: 5, resolved: 5, sla: 100, backlog: 0, step: 1 },
  { id: 'W05', cases: 11, resolved: 8, sla: 85, backlog: 3, step: 2 },
  { id: 'W06', cases: 19, resolved: 12, sla: 74, backlog: 7, step: 3 },
  { id: 'W07', cases: 34, resolved: 22, sla: 65, backlog: 12, step: 4 },
  { id: 'W08', cases: 3, resolved: 3, sla: 100, backlog: 0, step: 1 },
  { id: 'W09', cases: 22, resolved: 15, sla: 73, backlog: 7, step: 3 },
  { id: 'W10', cases: 6, resolved: 5, sla: 92, backlog: 1, step: 1 },
  { id: 'W11', cases: 15, resolved: 11, sla: 80, backlog: 4, step: 2 },
  { id: 'W12', cases: 45, resolved: 25, sla: 58, backlog: 20, step: 5 },
  { id: 'W13', cases: 9, resolved: 7, sla: 89, backlog: 2, step: 1 },
  { id: 'W14', cases: 12, resolved: 9, sla: 83, backlog: 3, step: 2 },
  { id: 'W15', cases: 7, resolved: 6, sla: 90, backlog: 1, step: 1 },
  { id: 'W16', cases: 20, resolved: 14, sla: 75, backlog: 6, step: 3 },
  { id: 'W17', cases: 16, resolved: 12, sla: 81, backlog: 4, step: 2 },
  { id: 'W18', cases: 38, resolved: 20, sla: 60, backlog: 18, step: 4 },
];

const METRICS = ['Active Cases', 'SLA Compliance', 'Backlog', 'Resolution Rate'];

function getHeatColor(step: number) {
  return `var(--heat-${step})`;
}
function getTextColor(step: number) {
  return step >= 4 ? 'var(--on-wine)' : 'var(--ink)';
}

const WardHeatmapPage: React.FC = () => {
  const [metric, setMetric] = useState('Active Cases');
  const [selectedWard, setSelectedWard] = useState<string | null>(null);
  const ward = wardsData.find(w => w.id === selectedWard);

  const [sortField, setSortField] = useState<keyof typeof wardsData[0]>('id');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  
  const handleSort = (field: keyof typeof wardsData[0]) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  };

  const sortedWards = [...wardsData].sort((a, b) => {
    const av = a[sortField], bv = b[sortField];
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  });

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A09</div>
        <h1 className="cc-title cc-headline-pop">Ward Heatmap</h1>
      </div>

      {/* Metric selector */}
      <div className="flex items-center gap-3 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        {METRICS.map(m => (
          <button
            key={m}
            onClick={() => setMetric(m)}
            className={`cc-chip cursor-pointer transition-colors ${metric === m ? 'bg-lime text-ink border-ink' : 'hover:bg-lime-tint'}`}
          >
            {m}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Heat tiles */}
        <div className="lg:col-span-2">
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-sm text-ink">Schematic Ward View</h3>
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map(s => (
                  <div key={s} className="w-4 h-4 rounded border border-ink/30" style={{ background: getHeatColor(s) }} />
                ))}
                <span className="text-[10px] font-mono text-muted ml-1">Low → High</span>
              </div>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
              {wardsData.map((w, i) => {
                let displayValue: string | number = w.cases;
                if (metric === 'SLA Compliance') displayValue = `${w.sla}%`;
                else if (metric === 'Backlog') displayValue = w.backlog;
                else if (metric === 'Resolution Rate') displayValue = `${Math.round(w.resolved / w.cases * 100)}%`;

                return (
                  <button
                    key={w.id}
                    onClick={() => setSelectedWard(w.id)}
                    className={`cc-heat-tile cc-card-lift cc-fade-up cursor-pointer ${selectedWard === w.id ? 'ring-3 ring-lime' : ''}`}
                    style={{ background: getHeatColor(w.step), color: getTextColor(w.step), '--stagger-index': i } as React.CSSProperties}
                  >
                    <div className="font-mono text-[10px] opacity-70">{w.id}</div>
                    <div className="font-display text-lg">{displayValue}</div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Ward detail panel */}
        <div className="lg:col-span-1">
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
            <h3 className="font-display text-sm text-ink mb-4">
              {ward ? `${ward.id} Detail` : 'Select a ward'}
            </h3>
            {ward ? (
              <div className="space-y-3">
                {[
                  { label: 'Active Cases', value: ward.cases },
                  { label: 'Resolved', value: ward.resolved },
                  { label: 'SLA Compliance', value: `${ward.sla}%` },
                  { label: 'Backlog', value: ward.backlog },
                  { label: 'Heat Step', value: ward.step },
                ].map(f => (
                  <div key={f.label} className="flex justify-between items-center py-2 border-b border-dot">
                    <span className="text-[10px] font-mono text-muted uppercase">{f.label}</span>
                    <span className="text-sm font-semibold text-ink">{f.value}</span>
                  </div>
                ))}
                <div className="mt-3">
                  <p className="text-[10px] font-mono text-muted uppercase mb-1">SLA</p>
                  <div className="cc-meter">
                    <div
                      className={`cc-meter-fill cc-bar-grow-x ${ward.sla >= 80 ? 'cc-meter-fill-lime' : 'cc-meter-fill-risk'}`}
                      style={{ width: `${ward.sla}%` }}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted font-mono py-8 text-center">Click a tile to see details</p>
            )}
          </div>
        </div>
      </div>

      {/* Full ward table */}
      <div className="cc-card cc-fade-up" style={{ '--stagger-index': 3 } as React.CSSProperties}>
        <div className="px-5 py-3 border-b-2 border-ink">
          <h3 className="font-display text-sm text-ink">All Wards</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
            <thead>
              <tr>
                {(['id', 'cases', 'resolved', 'sla', 'backlog', 'step'] as const).map((col) => (
                  <th key={col} onClick={() => handleSort(col)} className="cursor-pointer select-none">
                    <span className="flex items-center gap-1">
                      {col === 'id' ? 'Ward' : col === 'step' ? 'Heat' : col === 'sla' ? 'SLA' : col.charAt(0).toUpperCase() + col.slice(1)}
                      <ArrowUpDown className="h-3 w-3 opacity-40" />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedWards.map((w, i) => (
                <tr key={w.id} className="cc-fade-up cursor-pointer hover:bg-lime-tint"
                  style={{ '--stagger-index': i } as React.CSSProperties}
                  onClick={() => setSelectedWard(w.id)}
                >
                  <td className="font-mono font-semibold" style={{ color: 'var(--wine)' }}>{w.id}</td>
                  <td className="font-mono">{w.cases}</td>
                  <td className="font-mono">{w.resolved}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="cc-meter flex-1" style={{ maxWidth: '80px' }}>
                        <div className={`cc-meter-fill ${w.sla >= 80 ? 'cc-meter-fill-lime' : 'cc-meter-fill-risk'}`}
                          style={{ width: `${w.sla}%` }} />
                      </div>
                      <span className="text-xs font-mono">{w.sla}%</span>
                    </div>
                  </td>
                  <td className="font-mono">{w.backlog}</td>
                  <td>
                    <div className="w-6 h-6 rounded border border-ink/30 inline-block"
                      style={{ background: getHeatColor(w.step) }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default WardHeatmapPage;
