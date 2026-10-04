/**
 * O03 — Issues (Overlooker view)
 * Read-only case browser with filters, cc-table with priority/status chips,
 * and a read-only detail drawer. No mutations allowed.
 *
 * Data: GET /cases (same as admin, but the overlooker sees all cities).
 */
import React, { useState } from 'react';
import { Search, Eye, X, ChevronLeft, ChevronRight } from 'lucide-react';

interface Issue {
  id: string;
  title: string;
  location: string;
  category: string;
  status: string;
  priority: string;
  ward: string;
  timeAgo: string;
}

const mockIssues: Issue[] = [
  { id: 'CC-1042', title: 'Major pothole near school', location: 'MG Road, W12', category: 'Roads', status: 'in_progress', priority: 'URGENT', ward: 'W12', timeAgo: '5d ago' },
  { id: 'CC-1038', title: 'Raw sewage overflow', location: 'Station Road, W18', category: 'Sanitation', status: 'submitted', priority: 'HIGH', ward: 'W18', timeAgo: '3d ago' },
  { id: 'CC-1031', title: 'Street lighting failure', location: 'Civil Lines, W7', category: 'Electrical', status: 'submitted', priority: 'HIGH', ward: 'W7', timeAgo: '6d ago' },
  { id: 'CC-1027', title: 'Water supply disruption', location: 'Main Market, W3', category: 'Water', status: 'in_progress', priority: 'URGENT', ward: 'W3', timeAgo: '2d ago' },
  { id: 'CC-1019', title: 'Garbage accumulation', location: 'Park Area, W9', category: 'Sanitation', status: 'resolved', priority: 'NORMAL', ward: 'W9', timeAgo: '4d ago' },
  { id: 'CC-1015', title: 'Blocked drainage', location: 'Lake Road, W5', category: 'Drainage', status: 'resolved', priority: 'LOW', ward: 'W5', timeAgo: '7d ago' },
];

function PriorityChip({ p }: { p: string }) {
  const cls: Record<string, string> = { URGENT: 'cc-priority-urgent', HIGH: 'cc-priority-high', NORMAL: 'cc-priority-normal', LOW: 'cc-priority-low' };
  return <span className={`cc-chip text-[10px] ${cls[p] ?? ''}`}>{p}</span>;
}

function StatusChip({ s }: { s: string }) {
  const map: Record<string, string> = {
    submitted: 'bg-lime-tint text-ink', in_progress: 'bg-amber text-ink',
    resolved: 'bg-lime text-ink', rejected: 'bg-fire text-on-fire',
  };
  const labels: Record<string, string> = { submitted: 'Submitted', in_progress: 'In Progress', resolved: 'Resolved' };
  return <span className={`cc-chip text-[10px] ${map[s] ?? ''}`}>{labels[s] ?? s}</span>;
}

const IssuesPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = mockIssues.find(i => i.id === selectedId);

  const filtered = mockIssues.filter(i =>
    !query || i.title.toLowerCase().includes(query.toLowerCase()) || i.id.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">O03</div>
        <h1 className="cc-title cc-headline-pop">Issues</h1>
        <p className="text-xs font-mono text-muted mt-1">Read-only case browser</p>
      </div>

      {/* Search */}
      <div className="cc-card p-4 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="text"
            placeholder="Search cases..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted"
            style={{ minHeight: '44px' }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="cc-card cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
        <div className="overflow-x-auto">
          <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
            <thead>
              <tr>
                <th>Case</th>
                <th>Title</th>
                <th>Location</th>
                <th>Category</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Ward</th>
                <th>Age</th>
                <th style={{ width: '60px' }}>View</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((issue, i) => (
                <tr key={issue.id} className="cc-fade-up cursor-pointer" style={{ '--stagger-index': i } as React.CSSProperties}
                  onClick={() => setSelectedId(issue.id)}>
                  <td className="font-mono text-xs font-semibold" style={{ color: 'var(--wine)' }}>{issue.id}</td>
                  <td className="max-w-[180px] truncate">{issue.title}</td>
                  <td className="text-muted">{issue.location}</td>
                  <td className="text-muted">{issue.category}</td>
                  <td><StatusChip s={issue.status} /></td>
                  <td><PriorityChip p={issue.priority} /></td>
                  <td className="font-mono text-muted">{issue.ward}</td>
                  <td className="font-mono text-muted text-xs">{issue.timeAgo}</td>
                  <td>
                    <button className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint transition-colors">
                      <Eye className="h-3 w-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Read-only detail drawer */}
      {selected && (
        <>
          <div className="fixed inset-0 bg-ink/20 z-30" onClick={() => setSelectedId(null)} />
          <div className="fixed inset-y-0 right-0 w-96 z-40 cc-card cc-fade-up"
            style={{ borderRadius: 'var(--radius-lg) 0 0 var(--radius-lg)', borderRight: 'none', '--stagger-index': 0 } as React.CSSProperties}>
            <div className="h-full overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b-2 border-ink">
                <div>
                  <p className="font-mono text-xs text-muted">{selected.id}</p>
                  <h3 className="font-display text-lg text-ink mt-1">{selected.title}</h3>
                </div>
                <button onClick={() => setSelectedId(null)} className="w-8 h-8 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <PriorityChip p={selected.priority} />
                  <StatusChip s={selected.status} />
                </div>
                {[
                  { label: 'Location', value: selected.location },
                  { label: 'Category', value: selected.category },
                  { label: 'Ward', value: selected.ward },
                  { label: 'Reported', value: selected.timeAgo },
                ].map(f => (
                  <div key={f.label} className="flex justify-between items-center py-2 border-b border-dot">
                    <span className="text-[10px] font-mono text-muted uppercase">{f.label}</span>
                    <span className="text-sm font-medium text-ink">{f.value}</span>
                  </div>
                ))}
                <div className="cc-banner-degraded mt-4 text-xs">
                  Read-only view. Contact admin for case actions.
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default IssuesPage;