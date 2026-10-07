/**
 * O03 — Issues (Overlooker view)
 * Full-page read-only case browser with filters, priority/status chips,
 * and an inline detail panel. No mutations allowed.
 *
 * Data: GET /cases (same as admin, but the overlooker sees all cities).
 */
import React, { useState, useMemo } from 'react';
import { Search, Eye, X, Filter, MapPin, Clock, Tag, Hash, ChevronUp, ChevronDown } from 'lucide-react';

interface Issue {
  id: string;
  title: string;
  location: string;
  category: string;
  status: string;
  priority: string;
  ward: string;
  timeAgo: string;
  description?: string;
}

const mockIssues: Issue[] = [
  { id: 'CC-1042', title: 'Major pothole near school', location: 'MG Road, W12', category: 'Roads', status: 'in_progress', priority: 'URGENT', ward: 'W12', timeAgo: '5d ago', description: 'Large pothole ~1.2m wide has formed near St. Xavier School gate, causing vehicle damage and safety hazards for students. Multiple reports filed from parents.' },
  { id: 'CC-1038', title: 'Raw sewage overflow', location: 'Station Road, W18', category: 'Sanitation', status: 'submitted', priority: 'HIGH', ward: 'W18', timeAgo: '3d ago', description: 'Sewage overflowing from manhole since morning. Affecting 200+ residents in the area. Health risk is significant.' },
  { id: 'CC-1031', title: 'Street lighting failure', location: 'Civil Lines, W7', category: 'Electrical', status: 'submitted', priority: 'HIGH', ward: 'W7', timeAgo: '6d ago', description: '14 streetlights non-functional on the 800m Civil Lines stretch. Area has seen 2 theft incidents since the outage began.' },
  { id: 'CC-1027', title: 'Water supply disruption', location: 'Main Market, W3', category: 'Water', status: 'in_progress', priority: 'URGENT', ward: 'W3', timeAgo: '2d ago', description: 'No water supply for 300 households for over 48 hours. Pipe damage suspected near junction. Tankers deployed as interim measure.' },
  { id: 'CC-1019', title: 'Garbage accumulation', location: 'Park Area, W9', category: 'Sanitation', status: 'resolved', priority: 'NORMAL', ward: 'W9', timeAgo: '4d ago', description: 'Uncollected waste for 5 days at Park Area junction. Resolved after crew dispatch on day 4.' },
  { id: 'CC-1015', title: 'Blocked drainage', location: 'Lake Road, W5', category: 'Drainage', status: 'resolved', priority: 'LOW', ward: 'W5', timeAgo: '7d ago', description: 'Stormwater drain blocked by debris near Lake Road crossing. Cleared by maintenance crew.' },
  { id: 'CC-1008', title: 'Road crack near market', location: 'Market Rd, W4', category: 'Roads', status: 'in_progress', priority: 'HIGH', ward: 'W4', timeAgo: '9d ago', description: 'Long crack (12m) along market road, creating trip hazard and water pooling during rains.' },
  { id: 'CC-0997', title: 'Broken footpath tiles', location: 'Gandhi Nagar, W11', category: 'Roads', status: 'submitted', priority: 'NORMAL', ward: 'W11', timeAgo: '11d ago', description: 'Multiple footpath tiles broken across Gandhi Nagar stretch, creating accessibility issues for elderly residents.' },
];

const PRIORITY_ORDER: Record<string, number> = { URGENT: 0, HIGH: 1, NORMAL: 2, LOW: 3 };
const STATUS_LABELS: Record<string, string> = { submitted: 'Submitted', in_progress: 'In Progress', resolved: 'Resolved', rejected: 'Rejected' };

function PriorityChip({ p }: { p: string }) {
  const cls: Record<string, string> = { URGENT: 'cc-priority-urgent', HIGH: 'cc-priority-high', NORMAL: 'cc-priority-normal', LOW: 'cc-priority-low' };
  return <span className={`cc-chip text-[10px] ${cls[p] ?? ''}`}>{p}</span>;
}

function StatusChip({ s }: { s: string }) {
  const map: Record<string, string> = {
    submitted: 'bg-lime-tint text-ink', in_progress: 'bg-amber text-ink',
    resolved: 'bg-lime text-ink', rejected: 'bg-fire text-on-fire',
  };
  return <span className={`cc-chip text-[10px] ${map[s] ?? ''}`}>{STATUS_LABELS[s] ?? s}</span>;
}

type SortField = 'id' | 'priority' | 'timeAgo';
type SortDir = 'asc' | 'desc';

const IssuesPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('priority');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const selected = mockIssues.find(i => i.id === selectedId);

  const filtered = useMemo(() => {
    let list = mockIssues.filter(i =>
      (!query || i.title.toLowerCase().includes(query.toLowerCase()) || i.id.toLowerCase().includes(query.toLowerCase()) || i.location.toLowerCase().includes(query.toLowerCase())) &&
      (statusFilter === 'all' || i.status === statusFilter) &&
      (priorityFilter === 'all' || i.priority === priorityFilter)
    );
    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortField === 'priority') cmp = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
      else if (sortField === 'id') cmp = b.id.localeCompare(a.id);
      else if (sortField === 'timeAgo') cmp = a.timeAgo.localeCompare(b.timeAgo);
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [query, statusFilter, priorityFilter, sortField, sortDir]);

  function toggleSort(field: SortField) {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? <ChevronUp className="inline h-3 w-3 ml-1" /> : <ChevronDown className="inline h-3 w-3 ml-1" />;
  }

  const urgentCount = filtered.filter(i => i.priority === 'URGENT' && i.status !== 'resolved').length;
  const resolvedCount = filtered.filter(i => i.status === 'resolved').length;

  return (
    <div className="flex flex-col" style={{ minHeight: 'calc(100vh - 64px)' }}>
      {/* ── Page Header ─────────────────────────────────────────────── */}
      <div className="cc-page-header mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="cc-eyebrow cc-fade-up">O03</div>
            <h1 className="cc-title cc-headline-pop">Issues</h1>
            <p className="text-xs font-mono text-muted mt-1">Read-only case browser — {mockIssues.length} total cases</p>
          </div>
          {/* KPI pills */}
          <div className="hidden sm:flex items-center gap-3 mt-2">
            <div className="cc-card px-3 py-2 text-center">
              <p className="font-display text-xl text-ink">{urgentCount}</p>
              <p className="text-[10px] font-mono text-muted">Urgent Active</p>
            </div>
            <div className="cc-card px-3 py-2 text-center">
              <p className="font-display text-xl" style={{ color: 'var(--lime)' }}>{resolvedCount}</p>
              <p className="text-[10px] font-mono text-muted">Resolved</p>
            </div>
            <div className="cc-card px-3 py-2 text-center">
              <p className="font-display text-xl text-ink">{filtered.length}</p>
              <p className="text-[10px] font-mono text-muted">Filtered</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Search + Filters ────────────────────────────────────────── */}
      <div className="cc-card p-4 cc-fade-up mb-4" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              id="issues-search"
              type="text"
              placeholder="Search by case ID, title, location…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted focus:outline-none focus:border-lime transition-colors"
              style={{ minHeight: '44px' }}
            />
          </div>
          {/* Status filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-muted shrink-0" />
            <select
              id="issues-status-filter"
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="bg-ground border-2 border-ink rounded-md text-sm text-ink py-2 px-3 focus:outline-none focus:border-lime transition-colors"
              style={{ minHeight: '44px' }}
            >
              <option value="all">All Statuses</option>
              <option value="submitted">Submitted</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          {/* Priority filter */}
          <select
            id="issues-priority-filter"
            value={priorityFilter}
            onChange={e => setPriorityFilter(e.target.value)}
            className="bg-ground border-2 border-ink rounded-md text-sm text-ink py-2 px-3 focus:outline-none focus:border-lime transition-colors"
            style={{ minHeight: '44px' }}
          >
            <option value="all">All Priorities</option>
            <option value="URGENT">Urgent</option>
            <option value="HIGH">High</option>
            <option value="NORMAL">Normal</option>
            <option value="LOW">Low</option>
          </select>
        </div>
      </div>

      {/* ── Main content: table + detail panel ──────────────────────── */}
      <div className={`flex gap-4 flex-1 min-h-0 cc-fade-up`} style={{ '--stagger-index': 1 } as React.CSSProperties}>

        {/* Table */}
        <div className={`cc-card overflow-hidden flex flex-col transition-all duration-300 ${selected ? 'flex-1 min-w-0' : 'w-full'}`}>
          {/* Table header */}
          <div className="flex items-center justify-between px-4 py-3 border-b-2" style={{ borderColor: 'color-mix(in srgb, var(--ink) 12%, transparent)' }}>
            <p className="text-xs font-mono text-muted">{filtered.length} case{filtered.length !== 1 ? 's' : ''} shown</p>
            <div className="flex gap-2">
              <button
                onClick={() => toggleSort('priority')}
                className={`text-[10px] font-mono px-2 py-1 rounded border transition-colors ${sortField === 'priority' ? 'border-ink bg-ink text-on-wine' : 'border-dot text-muted hover:border-ink hover:text-ink'}`}
              >
                Priority <SortIcon field="priority" />
              </button>
              <button
                onClick={() => toggleSort('id')}
                className={`text-[10px] font-mono px-2 py-1 rounded border transition-colors ${sortField === 'id' ? 'border-ink bg-ink text-on-wine' : 'border-dot text-muted hover:border-ink hover:text-ink'}`}
              >
                Case ID <SortIcon field="id" />
              </button>
            </div>
          </div>

          {/* Table body */}
          <div className="overflow-y-auto flex-1">
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Search className="h-10 w-10 text-muted/40 mb-3" />
                <p className="font-mono text-sm text-muted">No cases match your filters</p>
                <button onClick={() => { setQuery(''); setStatusFilter('all'); setPriorityFilter('all'); }} className="mt-3 text-xs font-mono text-wine underline">Clear filters</button>
              </div>
            ) : (
              <table className="cc-table w-full" style={{ border: 'none', borderRadius: 0 }}>
                <thead className="sticky top-0 bg-ground z-10">
                  <tr>
                    <th className="text-left">Case</th>
                    <th className="text-left">Title</th>
                    {!selected && <th className="text-left hidden md:table-cell">Location</th>}
                    {!selected && <th className="text-left hidden lg:table-cell">Category</th>}
                    <th className="text-left">Status</th>
                    <th className="text-left">Priority</th>
                    {!selected && <th className="text-left hidden sm:table-cell">Ward</th>}
                    {!selected && <th className="text-left hidden sm:table-cell">Age</th>}
                    <th style={{ width: '48px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((issue, i) => (
                    <tr
                      key={issue.id}
                      className={`cc-fade-up cursor-pointer transition-colors ${selectedId === issue.id ? 'bg-lime-tint/50' : 'hover:bg-ground'}`}
                      style={{ '--stagger-index': i } as React.CSSProperties}
                      onClick={() => setSelectedId(issue.id === selectedId ? null : issue.id)}
                    >
                      <td className="font-mono text-xs font-semibold whitespace-nowrap" style={{ color: 'var(--wine)' }}>{issue.id}</td>
                      <td className={`font-medium ${selected ? 'max-w-[140px]' : 'max-w-[220px]'} truncate`}>{issue.title}</td>
                      {!selected && <td className="text-muted hidden md:table-cell">{issue.location}</td>}
                      {!selected && <td className="text-muted hidden lg:table-cell">{issue.category}</td>}
                      <td><StatusChip s={issue.status} /></td>
                      <td><PriorityChip p={issue.priority} /></td>
                      {!selected && <td className="font-mono text-muted hidden sm:table-cell">{issue.ward}</td>}
                      {!selected && <td className="font-mono text-muted text-xs hidden sm:table-cell">{issue.timeAgo}</td>}
                      <td>
                        <button
                          id={`view-case-${issue.id}`}
                          className={`w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center transition-colors ${selectedId === issue.id ? 'bg-ink' : 'hover:bg-lime-tint'}`}
                        >
                          {selectedId === issue.id
                            ? <X className="h-3 w-3 text-on-wine" />
                            : <Eye className="h-3 w-3" />
                          }
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ── Inline Detail Panel ────────────────────────────────────── */}
        {selected && (
          <div
            className="cc-card flex flex-col cc-fade-up overflow-hidden"
            style={{ width: '340px', minWidth: '280px', '--stagger-index': 0 } as React.CSSProperties}
          >
            {/* Panel header */}
            <div className="flex items-start justify-between p-5 border-b-2" style={{ borderColor: 'color-mix(in srgb, var(--ink) 12%, transparent)' }}>
              <div className="flex-1 min-w-0">
                <p className="font-mono text-[10px] text-muted uppercase tracking-wider">{selected.id}</p>
                <h3 className="font-display text-base text-ink mt-1 leading-snug">{selected.title}</h3>
              </div>
              <button
                onClick={() => setSelectedId(null)}
                className="w-8 h-8 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint transition-colors shrink-0 ml-2"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Panel body */}
            <div className="p-5 overflow-y-auto flex-1 space-y-4">
              {/* Chips */}
              <div className="flex items-center gap-2 flex-wrap">
                <PriorityChip p={selected.priority} />
                <StatusChip s={selected.status} />
              </div>

              {/* Description */}
              {selected.description && (
                <div className="cc-card p-3" style={{ background: 'var(--ground)' }}>
                  <p className="text-[10px] font-mono text-muted uppercase tracking-wider mb-2">Description</p>
                  <p className="text-sm text-ink leading-relaxed">{selected.description}</p>
                </div>
              )}

              {/* Metadata fields */}
              <div className="space-y-0 border-2 rounded-md overflow-hidden" style={{ borderColor: 'color-mix(in srgb, var(--ink) 12%, transparent)' }}>
                {[
                  { label: 'Location', value: selected.location, Icon: MapPin },
                  { label: 'Category', value: selected.category, Icon: Tag },
                  { label: 'Ward', value: selected.ward, Icon: Hash },
                  { label: 'Reported', value: selected.timeAgo, Icon: Clock },
                ].map((f, idx) => (
                  <div key={f.label} className={`flex items-center justify-between px-4 py-3 ${idx < 3 ? 'border-b' : ''}`} style={{ borderColor: 'color-mix(in srgb, var(--ink) 10%, transparent)' }}>
                    <div className="flex items-center gap-2">
                      <f.Icon className="h-3.5 w-3.5 text-muted shrink-0" />
                      <span className="text-[10px] font-mono text-muted uppercase tracking-wide">{f.label}</span>
                    </div>
                    <span className="text-sm font-medium text-ink">{f.value}</span>
                  </div>
                ))}
              </div>

              {/* Read-only notice */}
              <div className="cc-banner-degraded text-xs">
                Read-only view. Contact admin for case actions.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default IssuesPage;