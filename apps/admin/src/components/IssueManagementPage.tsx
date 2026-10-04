/**
 * A03 — Case Workbench
 * Filter bar, folder-tab saved views with counts, dense table with selection,
 * preview drawer, bulk action bar.
 *
 * Data: GET /cases with q, status, category, priority, ward_id, department_id,
 *       from, until, sort, cursor, limit (cursor pagination).
 * Drawer reads GET /cases/{id}. Bulk Assign uses /triage/decision.
 * Gap: escalate, merge and request information have no endpoints; hide them.
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Eye, ArrowUpRight, X, ChevronLeft, ChevronRight } from 'lucide-react';

interface Issue {
  id: string;
  location: string;
  category: string;
  status: 'submitted' | 'in_progress' | 'resolved' | 'rejected' | 'verified';
  assignedTo: string;
  priority: 'URGENT' | 'HIGH' | 'NORMAL' | 'LOW';
  ward: string;
  timeAgo: string;
  description: string;
  selected?: boolean;
}

const mockIssues: Issue[] = [
  { id: 'CC-1042', location: 'MG Road, W12', category: 'Roads', status: 'in_progress', assignedTo: 'Road Dept', priority: 'URGENT', ward: 'W12', timeAgo: '5d ago', description: 'Major pothole near school — recurring' },
  { id: 'CC-1038', location: 'Station Road, W18', category: 'Sanitation', status: 'submitted', assignedTo: 'Sanitation', priority: 'HIGH', ward: 'W18', timeAgo: '3d ago', description: 'Raw sewage overflow, residential block' },
  { id: 'CC-1031', location: 'Civil Lines, W7', category: 'Electrical', status: 'submitted', assignedTo: 'Electrical', priority: 'HIGH', ward: 'W7', timeAgo: '6d ago', description: 'Street lighting failure — 200m stretch' },
  { id: 'CC-1027', location: 'Main Market, W3', category: 'Water', status: 'in_progress', assignedTo: 'Water', priority: 'URGENT', ward: 'W3', timeAgo: '2d ago', description: 'Water supply disruption — 300 households' },
  { id: 'CC-1019', location: 'Park Area, W9', category: 'Sanitation', status: 'resolved', assignedTo: 'Sanitation', priority: 'NORMAL', ward: 'W9', timeAgo: '4d ago', description: 'Garbage accumulation — market area' },
  { id: 'CC-1015', location: 'Lake Road, W5', category: 'Drainage', status: 'verified', assignedTo: 'Drainage', priority: 'LOW', ward: 'W5', timeAgo: '7d ago', description: 'Blocked drain near residential area' },
  { id: 'CC-1011', location: 'Temple Road, W2', category: 'Roads', status: 'submitted', assignedTo: 'Road Dept', priority: 'NORMAL', ward: 'W2', timeAgo: '1d ago', description: 'Road surface damage after rain' },
];

// Priority chip per the plan — priority is never colour-only, text label always printed
function PriorityChip({ priority }: { priority: string }) {
  const cls: Record<string, string> = {
    URGENT: 'cc-priority-urgent',
    HIGH:   'cc-priority-high',
    NORMAL: 'cc-priority-normal',
    LOW:    'cc-priority-low',
  };
  return (
    <span className={`cc-chip text-[11px] ${cls[priority] ?? 'cc-priority-normal'}`}>
      {priority}
    </span>
  );
}

// Status chip — text label always printed
function StatusChip({ status }: { status: string }) {
  const labels: Record<string, string> = {
    submitted: 'Submitted',
    in_progress: 'In Progress',
    resolved: 'Resolved',
    rejected: 'Rejected',
    verified: 'Verified',
  };
  const tones: Record<string, string> = {
    submitted: 'border-ink bg-lime-tint text-ink',
    in_progress: 'border-ink bg-amber text-ink',
    resolved: 'border-ink bg-lime text-ink',
    rejected: 'border-ink bg-fire text-on-fire',
    verified: 'border-ink bg-surface text-ink',
  };
  return (
    <span className={`cc-chip text-[11px] ${tones[status] ?? ''}`}>
      {labels[status] ?? status}
    </span>
  );
}

const IssueManagementPage: React.FC = () => {
  const [issues, setIssues] = useState<Issue[]>(mockIssues);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: 'all',
    priority: 'all',
    department: 'all',
    ward: 'all',
  });

  const handleSelectAll = (checked: boolean) => {
    setIssues(issues.map(issue => ({ ...issue, selected: checked })));
  };

  const handleSelectIssue = (id: string, checked: boolean) => {
    setIssues(issues.map(issue =>
      issue.id === id ? { ...issue, selected: checked } : issue
    ));
  };

  const selectedCount = issues.filter(i => i.selected).length;
  const selectedIssue = issues.find(i => i.id === selectedIssueId);

  const filteredIssues = issues.filter(issue => {
    if (searchQuery && !issue.location.toLowerCase().includes(searchQuery.toLowerCase()) && !issue.id.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    if (filters.status !== 'all' && issue.status !== filters.status) return false;
    if (filters.priority !== 'all' && issue.priority !== filters.priority) return false;
    if (filters.ward !== 'all' && issue.ward !== filters.ward) return false;
    return true;
  });

  const tabs = [
    { id: 'all', label: 'All Cases', count: issues.length },
    { id: 'submitted', label: 'New', count: issues.filter(i => i.status === 'submitted').length },
    { id: 'in_progress', label: 'In Progress', count: issues.filter(i => i.status === 'in_progress').length },
    { id: 'resolved', label: 'Resolved', count: issues.filter(i => i.status === 'resolved').length },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A03</div>
        <h1 className="cc-title cc-headline-pop">Case Workbench</h1>
      </div>

      {/* Filter bar */}
      <div className="cc-card p-4 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              placeholder="Search by ID, location, description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted"
              style={{ minHeight: '44px' }}
              aria-label="Search cases"
            />
          </div>

          {/* Status filter */}
          <select
            value={filters.status}
            onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
            className="px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink font-medium"
            style={{ minHeight: '44px' }}
            aria-label="Filter by status"
          >
            <option value="all">All Status</option>
            <option value="submitted">Submitted</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="verified">Verified</option>
          </select>

          {/* Priority filter */}
          <select
            value={filters.priority}
            onChange={(e) => setFilters(prev => ({ ...prev, priority: e.target.value }))}
            className="px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink font-medium"
            style={{ minHeight: '44px' }}
            aria-label="Filter by priority"
          >
            <option value="all">All Priority</option>
            <option value="URGENT">Urgent</option>
            <option value="HIGH">High</option>
            <option value="NORMAL">Normal</option>
            <option value="LOW">Low</option>
          </select>

          {/* Ward filter */}
          <select
            value={filters.ward}
            onChange={(e) => setFilters(prev => ({ ...prev, ward: e.target.value }))}
            className="px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink font-medium"
            style={{ minHeight: '44px' }}
            aria-label="Filter by ward"
          >
            <option value="all">All Wards</option>
            {Array.from({ length: 20 }, (_, i) => (
              <option key={i} value={`W${i + 1}`}>W{i + 1}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Folder tabs */}
      <div className="cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
        <div className="cc-folder-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                if (tab.id !== 'all') setFilters(prev => ({ ...prev, status: tab.id }));
                else setFilters(prev => ({ ...prev, status: 'all' }));
              }}
              className={`cc-folder-tab ${activeTab === tab.id ? 'cc-folder-tab-active' : ''}`}
            >
              {tab.label}
              <span className="ml-2 cc-chip text-[9px] py-0 px-1.5 border-ink/30">
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Bulk action bar + table */}
        <div className="cc-card" style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0, borderTop: 'none' }}>
          {/* Bulk actions */}
          <div className="px-5 py-3 border-b-2 border-ink flex items-center justify-between">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={filteredIssues.length > 0 && filteredIssues.every(i => i.selected)}
                onChange={(e) => handleSelectAll(e.target.checked)}
                className="w-4 h-4 rounded border-2 border-ink"
                aria-label="Select all issues"
              />
              <span className="text-xs font-mono text-muted">
                {selectedCount > 0 ? `${selectedCount} selected` : `${filteredIssues.length} cases`}
              </span>
              {selectedCount > 0 && (
                <div className="flex items-center gap-2 ml-4">
                  <button className="cc-btn cc-btn-primary text-xs py-1 px-3">
                    Bulk Assign
                  </button>
                  {/* Gap: escalate, merge, request-info hidden until endpoints exist */}
                </div>
              )}
            </div>
            <span className="text-xs font-mono text-muted">
              Page 1 of 1
            </span>
          </div>

          {/* Dense table */}
          <div className="overflow-x-auto" style={{ maxHeight: '500px' }}>
            <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
              <thead>
                <tr>
                  <th style={{ width: '40px' }}></th>
                  <th>Case</th>
                  <th>Location</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Assigned</th>
                  <th>Age</th>
                  <th style={{ width: '80px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredIssues.map((issue, i) => (
                  <tr
                    key={issue.id}
                    className="cc-fade-up cursor-pointer"
                    style={{ '--stagger-index': i } as React.CSSProperties}
                    onClick={() => setSelectedIssueId(issue.id)}
                  >
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={issue.selected || false}
                        onChange={(e) => handleSelectIssue(issue.id, e.target.checked)}
                        className="w-4 h-4 rounded border-2 border-ink"
                        aria-label={`Select case ${issue.id}`}
                      />
                    </td>
                    <td className="font-mono text-xs font-semibold" style={{ color: 'var(--wine)' }}>
                      {issue.id}
                    </td>
                    <td className="max-w-[200px] truncate">{issue.location}</td>
                    <td className="text-muted">{issue.category}</td>
                    <td><StatusChip status={issue.status} /></td>
                    <td><PriorityChip priority={issue.priority} /></td>
                    <td className="text-muted">{issue.assignedTo}</td>
                    <td className="font-mono text-muted text-xs">{issue.timeAgo}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-1">
                        <Link to={`/cases/${issue.id}`}>
                          <button
                            className="w-8 h-8 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint transition-colors"
                            aria-label={`View case ${issue.id}`}
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </button>
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="px-5 py-3 border-t-2 border-ink flex items-center justify-between">
            <span className="text-xs font-mono text-muted">
              Showing {filteredIssues.length} cases
            </span>
            <div className="flex items-center gap-2">
              <button className="cc-btn cc-btn-outline text-xs py-1 px-2" disabled aria-label="Previous page">
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <button className="cc-btn cc-btn-outline text-xs py-1 px-2" aria-label="Next page">
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Preview drawer (slides in from right when a row is clicked) */}
      {selectedIssue && (
        <div className="fixed inset-y-0 right-0 w-96 z-40 cc-card cc-fade-up"
          style={{
            borderRadius: 'var(--radius-lg) 0 0 var(--radius-lg)',
            borderRight: 'none',
            '--stagger-index': 0,
          } as React.CSSProperties}
        >
          <div className="h-full overflow-y-auto">
            {/* Drawer header */}
            <div className="flex items-center justify-between p-5 border-b-2 border-ink">
              <div>
                <p className="font-mono text-xs text-muted">{selectedIssue.id}</p>
                <h3 className="font-display text-lg text-ink mt-1">{selectedIssue.description}</h3>
              </div>
              <button
                onClick={() => setSelectedIssueId(null)}
                className="w-8 h-8 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint transition-colors"
                aria-label="Close drawer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Drawer content */}
            <div className="p-5 space-y-4">
              <div className="flex items-center gap-2">
                <PriorityChip priority={selectedIssue.priority} />
                <StatusChip status={selectedIssue.status} />
              </div>

              <div className="space-y-3">
                {[
                  { label: 'Location', value: selectedIssue.location },
                  { label: 'Category', value: selectedIssue.category },
                  { label: 'Ward', value: selectedIssue.ward },
                  { label: 'Assigned', value: selectedIssue.assignedTo },
                  { label: 'Reported', value: selectedIssue.timeAgo },
                ].map((field) => (
                  <div key={field.label} className="flex justify-between items-center py-2 border-b border-dot">
                    <span className="text-xs font-mono text-muted uppercase">{field.label}</span>
                    <span className="text-sm font-medium text-ink">{field.value}</span>
                  </div>
                ))}
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-4">
                <Link to={`/cases/${selectedIssue.id}`} className="flex-1">
                  <button className="cc-btn cc-btn-primary w-full justify-center text-sm">
                    Full Detail <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Backdrop for drawer */}
      {selectedIssue && (
        <div
          className="fixed inset-0 bg-ink/20 z-30"
          onClick={() => setSelectedIssueId(null)}
          aria-hidden="true"
        />
      )}
    </div>
  );
};

export default IssueManagementPage;