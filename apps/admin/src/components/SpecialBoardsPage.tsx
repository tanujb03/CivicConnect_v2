/**
 * A11 — Incidents / Special Boards
 * Quick-create incident form, active incidents board with status columns,
 * and incident detail cards.
 *
 * Data: GET /incidents?status=, POST /incidents, PATCH /incidents/{id}.
 */
import React, { useState } from 'react';
import { AlertTriangle, Plus, Clock, MapPin, Users } from 'lucide-react';

interface Incident {
  id: string;
  title: string;
  location: string;
  severity: 'CRITICAL' | 'HIGH' | 'NORMAL';
  status: 'active' | 'monitoring' | 'resolved';
  affectedWards: string[];
  reportedAt: string;
  casesLinked: number;
}

const mockIncidents: Incident[] = [
  { id: 'INC-001', title: 'Water main burst — W3 residential area', location: 'Main Market, W3', severity: 'CRITICAL', status: 'active', affectedWards: ['W3', 'W4'], reportedAt: '2h ago', casesLinked: 12 },
  { id: 'INC-002', title: 'Power grid failure — W7 sector', location: 'Civil Lines, W7', severity: 'HIGH', status: 'active', affectedWards: ['W7'], reportedAt: '4h ago', casesLinked: 8 },
  { id: 'INC-003', title: 'Sewage overflow after heavy rain', location: 'Station Road, W18', severity: 'HIGH', status: 'monitoring', affectedWards: ['W18', 'W19'], reportedAt: '1d ago', casesLinked: 15 },
  { id: 'INC-004', title: 'Road collapse near school zone', location: 'MG Road, W12', severity: 'CRITICAL', status: 'monitoring', affectedWards: ['W12'], reportedAt: '3d ago', casesLinked: 6 },
  { id: 'INC-005', title: 'Garbage collection disruption', location: 'Market area, W9', severity: 'NORMAL', status: 'resolved', affectedWards: ['W9', 'W10'], reportedAt: '5d ago', casesLinked: 4 },
];

function SeverityChip({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    CRITICAL: 'cc-priority-urgent',
    HIGH: 'cc-priority-high',
    NORMAL: 'cc-priority-normal',
  };
  return <span className={`cc-chip text-[10px] ${cls[severity] ?? ''}`}>{severity}</span>;
}

const columns = [
  { key: 'active' as const, label: 'Active', tone: 'bg-fire/10' },
  { key: 'monitoring' as const, label: 'Monitoring', tone: 'bg-amber/20' },
  { key: 'resolved' as const, label: 'Resolved', tone: 'bg-lime/20' },
];

const SpecialBoardsPage: React.FC<{ userRole?: string }> = ({ userRole }) => {
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A11</div>
        <h1 className="cc-title cc-headline-pop">Incidents</h1>
      </div>

      <div className="flex items-center gap-3 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <button className="cc-btn cc-btn-primary text-sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="h-4 w-4" /> Report Incident
        </button>
        <span className="cc-chip text-[10px] bg-fire text-on-fire">
          {mockIncidents.filter(i => i.status === 'active').length} active
        </span>
      </div>

      {/* Quick-create form */}
      {showCreate && (
        <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
          <h3 className="font-display text-sm text-ink mb-4">New Incident</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono text-muted uppercase">Title</label>
              <input type="text" placeholder="Incident title..." className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink" style={{ minHeight: '44px' }} />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono text-muted uppercase">Severity</label>
              <select className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink" style={{ minHeight: '44px' }}>
                <option>CRITICAL</option>
                <option>HIGH</option>
                <option>NORMAL</option>
              </select>
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-[10px] font-mono text-muted uppercase">Description</label>
              <textarea placeholder="Describe the incident..." rows={3} className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted resize-none" />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button className="cc-btn cc-btn-primary text-sm"><Plus className="h-4 w-4" /> Create</button>
            <button className="cc-btn cc-btn-outline text-sm" onClick={() => setShowCreate(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Three columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {columns.map((col, ci) => {
          const items = mockIncidents.filter(inc => inc.status === col.key);
          return (
            <div key={col.key} className="cc-fade-up" style={{ '--stagger-index': ci + 1 } as React.CSSProperties}>
              <div className="cc-card overflow-hidden">
                <div className={`px-4 py-3 border-b-2 border-ink ${col.tone}`}>
                  <div className="flex items-center justify-between">
                    <h3 className="font-display text-sm text-ink">{col.label}</h3>
                    <span className="cc-chip text-[9px] py-0 px-1.5">{items.length}</span>
                  </div>
                </div>
                <div className="p-3 space-y-3 min-h-[200px]">
                  {items.length === 0 && (
                    <div className="text-center text-xs font-mono text-muted py-8">No incidents</div>
                  )}
                  {items.map((inc, i) => (
                    <div key={inc.id} className="cc-card p-3 cc-card-lift cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-[10px] font-semibold" style={{ color: 'var(--wine)' }}>{inc.id}</span>
                        <SeverityChip severity={inc.severity} />
                      </div>
                      <p className="text-xs text-ink font-medium mb-2 line-clamp-2">{inc.title}</p>
                      <div className="space-y-1 text-[10px] font-mono text-muted">
                        <div className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {inc.location}</div>
                        <div className="flex items-center gap-1"><Clock className="h-3 w-3" /> {inc.reportedAt}</div>
                        <div className="flex items-center gap-1"><Users className="h-3 w-3" /> {inc.casesLinked} linked cases</div>
                      </div>
                      <div className="flex flex-wrap gap-1 mt-2 pt-2 border-t border-dot">
                        {inc.affectedWards.map(w => (
                          <span key={w} className="cc-chip text-[9px] py-0 px-1.5 border-muted/30">{w}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SpecialBoardsPage;
