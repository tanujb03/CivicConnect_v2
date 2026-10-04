/**
 * AnalyticsPage component (legacy — used by Index.tsx's old routing).
 * Simplified version that re-uses the Direction A tokens.
 */
import React from 'react';
import { BarChart3, TrendingUp } from 'lucide-react';

const trendData = [
  { label: 'W1', created: 45, resolved: 38 },
  { label: 'W2', created: 52, resolved: 44 },
  { label: 'W3', created: 48, resolved: 51 },
  { label: 'W4', created: 61, resolved: 42 },
];

const categories = [
  { name: 'Roads', count: 145 },
  { name: 'Lighting', count: 89 },
  { name: 'Garbage', count: 76 },
  { name: 'Water', count: 54 },
  { name: 'Drainage', count: 43 },
];

const AnalyticsPage: React.FC = () => {
  const maxCount = Math.max(...categories.map(c => c.count));

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A10</div>
        <h1 className="cc-title cc-headline-pop">Analytics</h1>
      </div>

      {/* Trend summary */}
      <div className="cc-card p-6 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <h3 className="font-display text-sm text-ink mb-4 flex items-center gap-2">
          <TrendingUp className="h-4 w-4" style={{ color: 'var(--wine)' }} />
          Weekly Trend
        </h3>
        <div className="grid grid-cols-4 gap-4">
          {trendData.map((week, i) => (
            <div key={week.label} className="cc-card p-3 text-center cc-card-lift cc-fade-up"
              style={{ '--stagger-index': i } as React.CSSProperties}>
              <p className="font-mono text-xs text-muted mb-1">{week.label}</p>
              <p className="font-display text-lg text-ink">{week.created}</p>
              <p className="text-[10px] font-mono text-lime">+{week.resolved} resolved</p>
            </div>
          ))}
        </div>
      </div>

      {/* Category breakdown */}
      <div className="cc-card p-6 cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
        <h3 className="font-display text-sm text-ink mb-4 flex items-center gap-2">
          <BarChart3 className="h-4 w-4" style={{ color: 'var(--wine)' }} />
          Category Breakdown
        </h3>
        <div className="space-y-3">
          {categories.map((cat, i) => (
            <div key={cat.name} className="cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-ink">{cat.name}</span>
                <span className="text-xs font-mono text-muted">{cat.count}</span>
              </div>
              <div className="cc-meter">
                <div
                  className="cc-meter-fill cc-meter-fill-lime cc-bar-grow-x"
                  style={{ width: `${(cat.count / maxCount) * 100}%`, '--stagger-index': i } as React.CSSProperties}
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