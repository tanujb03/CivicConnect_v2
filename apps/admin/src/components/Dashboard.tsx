/**
 * Dashboard component (legacy — used by Index.tsx's old routing).
 * Re-exports the new pages/Dashboard for backward compatibility.
 */
import React from 'react';
import RecentIssuesTable from './RecentIssuesTable';
import WardHeatmap from './WardHeatmap';
import DepartmentPerformance from './DepartmentPerformance';
import CityMap from './CityMap';
import { TrendingUp, FileText, Clock, Users } from 'lucide-react';

const kpis = [
  { label: 'Active Cases', value: '248', trend: '+12', up: true, icon: FileText },
  { label: 'Resolution Rate', value: '89%', trend: '+5%', up: true, icon: TrendingUp },
  { label: 'Avg Resolution', value: '4.2d', trend: '-12%', up: true, icon: Clock },
  { label: 'Active Citizens', value: '12.8K', trend: '+8%', up: true, icon: Users },
];

const Dashboard: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A02</div>
        <h1 className="cc-title cc-headline-pop">Operations Dashboard</h1>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpis.map((kpi, i) => {
          const Icon = kpi.icon;
          return (
            <div key={kpi.label} className="cc-kpi-card cc-card-lift cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
                  <Icon className="h-3.5 w-3.5 text-ink" />
                </div>
              </div>
              <p className="cc-kpi-value">{kpi.value}</p>
              <p className="cc-kpi-label">{kpi.label}</p>
              <p className={`text-xs font-mono font-semibold mt-1 ${kpi.up ? 'text-lime' : 'text-fire'}`}>{kpi.trend}</p>
            </div>
          );
        })}
      </div>

      {/* Map + Heatmap row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CityMap />
        <WardHeatmap />
      </div>

      {/* Recent Issues Table */}
      <RecentIssuesTable />

      {/* Department Performance */}
      <DepartmentPerformance />
    </div>
  );
};

export default Dashboard;