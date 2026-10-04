/**
 * A12 — Users
 * Role count cards, staff table with active toggles, user drawer,
 * read-only permission matrix.
 *
 * Gap: no user endpoints. Built against a useUsers() adapter.
 * Shows the needsBackend banner.
 */
import React, { useState } from 'react';
import { Users, Shield, Eye, X } from 'lucide-react';

const ROLES = [
  { role: 'Admin', count: 3, description: 'Full system access' },
  { role: 'Department Head', count: 6, description: 'Department-level management' },
  { role: 'Operator', count: 12, description: 'Case processing and triage' },
  { role: 'Field Worker', count: 24, description: 'On-site inspection and resolution' },
  { role: 'Overlooker', count: 4, description: 'Read-only city oversight' },
];

const mockUsers = [
  { id: '1', name: 'Admin Kumar', email: 'admin@ranchi.gov.in', role: 'Admin', department: 'City Administration', active: true },
  { id: '2', name: 'Priya Singh', email: 'priya@ranchi.gov.in', role: 'Department Head', department: 'Electrical', active: true },
  { id: '3', name: 'Rajesh Verma', email: 'rajesh@ranchi.gov.in', role: 'Operator', department: 'Road Maintenance', active: true },
  { id: '4', name: 'Sunita Devi', email: 'sunita@ranchi.gov.in', role: 'Department Head', department: 'Sanitation', active: true },
  { id: '5', name: 'Amit Sharma', email: 'amit@ranchi.gov.in', role: 'Field Worker', department: 'Water Works', active: false },
  { id: '6', name: 'Neha Gupta', email: 'neha@ranchi.gov.in', role: 'Operator', department: 'Garbage Management', active: true },
];

// Permission matrix from section 51A.18 (static, read-only)
const permissionMatrix = [
  { action: 'View cases', admin: true, deptHead: true, operator: true, field: true, overlooker: true },
  { action: 'Create cases', admin: true, deptHead: true, operator: true, field: false, overlooker: false },
  { action: 'Triage cases', admin: true, deptHead: false, operator: true, field: false, overlooker: false },
  { action: 'Assign departments', admin: true, deptHead: true, operator: false, field: false, overlooker: false },
  { action: 'Create work orders', admin: true, deptHead: true, operator: true, field: false, overlooker: false },
  { action: 'Update work orders', admin: true, deptHead: true, operator: true, field: true, overlooker: false },
  { action: 'Manage users', admin: true, deptHead: false, operator: false, field: false, overlooker: false },
  { action: 'System settings', admin: true, deptHead: false, operator: false, field: false, overlooker: false },
  { action: 'View analytics', admin: true, deptHead: true, operator: true, field: false, overlooker: true },
  { action: 'AI copilot', admin: true, deptHead: true, operator: true, field: false, overlooker: true },
];

const UserManagementPage: React.FC = () => {
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const selectedUser = mockUsers.find(u => u.id === selectedUserId);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A12</div>
        <h1 className="cc-title cc-headline-pop">Users</h1>
      </div>

      {/* Needs Backend banner */}
      <div className="cc-banner-needs-backend cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <Shield className="h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold text-sm">Needs Backend</p>
          <p className="text-xs">User management requires GET/PATCH /admin/users endpoints (audited). This screen shows static data.</p>
        </div>
      </div>

      {/* Role count cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {ROLES.map((r, i) => (
          <div key={r.role} className="cc-card p-4 cc-card-lift cc-fade-up" style={{ '--stagger-index': i + 1 } as React.CSSProperties}>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
                <Users className="h-3.5 w-3.5 text-ink" />
              </div>
            </div>
            <p className="font-display text-xl text-ink">{r.count}</p>
            <p className="text-[10px] font-mono text-muted uppercase mt-1">{r.role}</p>
          </div>
        ))}
      </div>

      {/* Staff table */}
      <div className="cc-card cc-fade-up" style={{ '--stagger-index': 6 } as React.CSSProperties}>
        <div className="px-5 py-3 border-b-2 border-ink">
          <h3 className="font-display text-sm text-ink">Staff Directory</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Department</th>
                <th>Status</th>
                <th style={{ width: '60px' }}>View</th>
              </tr>
            </thead>
            <tbody>
              {mockUsers.map((user, i) => (
                <tr key={user.id} className="cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
                  <td className="font-semibold text-ink">{user.name}</td>
                  <td className="font-mono text-xs text-muted">{user.email}</td>
                  <td><span className="cc-chip text-[10px]">{user.role}</span></td>
                  <td className="text-muted">{user.department}</td>
                  <td>
                    <span className={`cc-chip text-[10px] ${user.active ? 'bg-lime text-ink' : 'bg-dot text-muted'}`}>
                      {user.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => setSelectedUserId(user.id)}
                      className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint transition-colors"
                      aria-label={`View user ${user.name}`}
                    >
                      <Eye className="h-3 w-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Permission matrix — static, read-only */}
      <div className="cc-card cc-fade-up" style={{ '--stagger-index': 7 } as React.CSSProperties}>
        <div className="px-5 py-3 border-b-2 border-ink">
          <h3 className="font-display text-sm text-ink">Permission Matrix</h3>
          <p className="text-xs font-mono text-muted mt-0.5">Read-only, from section 51A.18</p>
        </div>
        <div className="overflow-x-auto">
          <table className="cc-table" style={{ border: 'none', borderRadius: 0 }}>
            <thead>
              <tr>
                <th>Action</th>
                <th>Admin</th>
                <th>Dept Head</th>
                <th>Operator</th>
                <th>Field</th>
                <th>Overlooker</th>
              </tr>
            </thead>
            <tbody>
              {permissionMatrix.map((row) => (
                <tr key={row.action}>
                  <td className="font-medium text-ink">{row.action}</td>
                  {[row.admin, row.deptHead, row.operator, row.field, row.overlooker].map((allowed, ci) => (
                    <td key={ci} className="text-center">
                      <span className={`inline-block w-5 h-5 rounded border-2 border-ink text-[10px] leading-5 font-bold ${
                        allowed ? 'bg-lime text-ink' : 'bg-ground text-muted'
                      }`}>
                        {allowed ? '✓' : '—'}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* User drawer */}
      {selectedUser && (
        <>
          <div className="fixed inset-0 bg-ink/20 z-30" onClick={() => setSelectedUserId(null)} aria-hidden="true" />
          <div className="fixed inset-y-0 right-0 w-96 z-40 cc-card cc-fade-up"
            style={{ borderRadius: 'var(--radius-lg) 0 0 var(--radius-lg)', borderRight: 'none', '--stagger-index': 0 } as React.CSSProperties}
          >
            <div className="h-full overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b-2 border-ink">
                <h3 className="font-display text-lg text-ink">{selectedUser.name}</h3>
                <button onClick={() => setSelectedUserId(null)} className="w-8 h-8 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint" aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="p-5 space-y-3">
                {[
                  { label: 'Email', value: selectedUser.email },
                  { label: 'Role', value: selectedUser.role },
                  { label: 'Department', value: selectedUser.department },
                  { label: 'Status', value: selectedUser.active ? 'Active' : 'Inactive' },
                ].map(f => (
                  <div key={f.label} className="flex justify-between items-center py-2 border-b border-dot">
                    <span className="text-[10px] font-mono text-muted uppercase">{f.label}</span>
                    <span className="text-sm font-medium text-ink">{f.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default UserManagementPage;
