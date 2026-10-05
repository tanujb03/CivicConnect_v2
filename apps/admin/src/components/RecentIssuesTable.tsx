/**
 * RecentIssuesTable — dashboard widget showing recent cases.
 * Uses cc-table styling with row stagger animation on mount.
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, ArrowUpDown } from 'lucide-react';

interface Issue {
  id: string;
  location: string;
  category: string;
  status: 'submitted' | 'progress' | 'resolved' | 'urgent';
  assignedTo: string;
  timeAgo: string;
}

const issuesData: Issue[] = [
  { id: 'CC-1042', location: 'MG Road, W12', category: 'Roads', status: 'urgent', assignedTo: 'Road Dept', timeAgo: '2h ago' },
  { id: 'CC-1038', location: 'Station Road, W18', category: 'Sanitation', status: 'submitted', assignedTo: 'Sanitation', timeAgo: '4h ago' },
  { id: 'CC-1031', location: 'Civil Lines, W7', category: 'Electrical', status: 'progress', assignedTo: 'Electrical', timeAgo: '6h ago' },
  { id: 'CC-1027', location: 'Main Market, W3', category: 'Water', status: 'urgent', assignedTo: 'Water', timeAgo: '3h ago' },
  { id: 'CC-1019', location: 'Park Area, W9', category: 'Sanitation', status: 'resolved', assignedTo: 'Sanitation', timeAgo: '1d ago' },
  { id: 'CC-1015', location: 'Lake Road, W5', category: 'Drainage', status: 'progress', assignedTo: 'Drainage', timeAgo: '5h ago' },
];

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    submitted: 'bg-lime-tint text-ink',
    progress: 'bg-amber text-ink',
    resolved: 'bg-lime text-ink',
    urgent: 'bg-fire text-on-fire',
  };
  const labels: Record<string, string> = {
    submitted: 'Submitted', progress: 'In Progress', resolved: 'Resolved', urgent: 'Urgent',
  };
  return (
    <span className={`cc-chip text-[10px] ${map[status] ?? ''}`}>
      {labels[status] ?? status}
    </span>
  );
}

const RecentIssuesTable: React.FC = () => {
  const [sortField, setSortField] = useState<keyof Issue>('id');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const navigate = useNavigate();

  const handleSort = (field: keyof Issue) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  };

  const sorted = [...issuesData].sort((a, b) => {
    const av = a[sortField], bv = b[sortField];
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  });

  return (
    <div className="cc-card">
      <div className="px-5 py-4 border-b-2 border-ink flex items-center justify-between">
        <div>
          <h3 className="font-display text-sm text-ink">Recent Cases</h3>
          <p className="text-xs font-mono text-muted mt-0.5">Latest reported issues</p>
        </div>
        <Link to="/cases">
          <button className="cc-btn cc-btn-outline text-xs py-1 px-3">
            View All
          </button>
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
          <thead>
            <tr>
              {(['id', 'location', 'category', 'status', 'assignedTo', 'timeAgo'] as const).map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className="cursor-pointer select-none"
                >
                  <span className="flex items-center gap-1">
                    {col === 'assignedTo' ? 'Assigned' : col === 'timeAgo' ? 'Age' : col.charAt(0).toUpperCase() + col.slice(1)}
                    <ArrowUpDown className="h-3 w-3 opacity-40" />
                  </span>
                </th>
              ))}
              <th style={{ width: '60px' }}>View</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((issue, i) => (
              <tr
                key={issue.id}
                className="cc-fade-up cursor-pointer hover:bg-ground"
                style={{ '--stagger-index': i } as React.CSSProperties}
                onClick={() => navigate(`/cases/${issue.id}`)}
              >
                <td className="font-mono text-xs font-semibold" style={{ color: 'var(--wine)' }}>{issue.id}</td>
                <td className="max-w-[180px] truncate">{issue.location}</td>
                <td className="text-muted">{issue.category}</td>
                <td><StatusChip status={issue.status} /></td>
                <td className="text-muted">{issue.assignedTo}</td>
                <td className="font-mono text-muted text-xs">{issue.timeAgo}</td>
                <td>
                  <Link to={`/cases/${issue.id}`} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint transition-colors"
                      aria-label={`View case ${issue.id}`}
                    >
                      <Eye className="h-3 w-3" />
                    </button>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RecentIssuesTable;
