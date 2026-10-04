/**
 * DepartmentPerformance — dashboard widget showing department load bars.
 * Uses cc-meter with token colors and cc-bar-grow-x animation.
 */
import React from 'react';

const departments = [
  { name: 'Road Maintenance', active: 45, resolved: 120, slaRate: 0.72 },
  { name: 'Sanitation', active: 38, resolved: 95, slaRate: 0.85 },
  { name: 'Electrical', active: 22, resolved: 78, slaRate: 0.91 },
  { name: 'Water Works', active: 18, resolved: 54, slaRate: 0.67 },
  { name: 'Garbage Mgmt', active: 31, resolved: 88, slaRate: 0.79 },
  { name: 'Public Works', active: 12, resolved: 42, slaRate: 0.93 },
];

const DepartmentPerformance: React.FC = () => {
  return (
    <div className="cc-card p-5 h-full">
      <div className="mb-4">
        <h3 className="font-display text-sm text-ink">Department Load</h3>
        <p className="text-xs font-mono text-muted mt-0.5">SLA compliance by department</p>
      </div>
      <div className="space-y-4">
        {departments.map((dept, i) => (
          <div key={dept.name} className="cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-ink truncate max-w-[140px]">{dept.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-muted">{dept.active} active</span>
                <span className={`cc-chip text-[9px] py-0 px-1.5 ${
                  dept.slaRate >= 0.85 ? 'bg-lime text-ink' :
                  dept.slaRate >= 0.7 ? 'bg-amber text-ink' :
                  'bg-fire text-on-fire'
                }`}>
                  {Math.round(dept.slaRate * 100)}%
                </span>
              </div>
            </div>
            <div className="cc-meter">
              <div
                className={`cc-meter-fill cc-bar-grow-x ${dept.slaRate >= 0.7 ? 'cc-meter-fill-lime' : 'cc-meter-fill-risk'}`}
                style={{
                  width: `${dept.slaRate * 100}%`,
                  '--stagger-index': i,
                } as React.CSSProperties}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] font-mono text-muted mt-4 pt-3 border-t border-dot">
        Caution: comparing departments with unequal workloads may be misleading.
      </p>
    </div>
  );
};

export default DepartmentPerformance;