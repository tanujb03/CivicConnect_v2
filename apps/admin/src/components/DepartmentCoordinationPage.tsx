/**
 * A06 — Departments
 * Three server-state columns (Assigned, In progress, Completed),
 * department filter, create-work-order form. No drag and drop.
 *
 * Data: GET /work-orders?status=&limit=, POST /cases/{id}/work-orders,
 *       PATCH /work-orders/{id}, POST /work-orders/{id}/cancel.
 *       Department filter runs in the browser because the endpoint
 *       filters by status only.
 */
import React, { useState } from 'react';
import { Building2, Clock, Users, Plus, ArrowUpRight, X } from 'lucide-react';

interface WorkOrder {
  id: string;
  caseId: string;
  title: string;
  department: string;
  priority: 'URGENT' | 'HIGH' | 'NORMAL' | 'LOW';
  status: 'assigned' | 'in_progress' | 'completed';
  assignedAt: string;
}

const mockWorkOrders: WorkOrder[] = [
  { id: 'WO-101', caseId: 'CC-1042', title: 'Repair major pothole near school', department: 'Road Maintenance', priority: 'URGENT', status: 'assigned', assignedAt: '2h ago' },
  { id: 'WO-098', caseId: 'CC-1038', title: 'Fix sewage overflow', department: 'Sanitation', priority: 'HIGH', status: 'assigned', assignedAt: '4h ago' },
  { id: 'WO-095', caseId: 'CC-1031', title: 'Restore street lighting', department: 'Electrical', priority: 'HIGH', status: 'in_progress', assignedAt: '1d ago' },
  { id: 'WO-092', caseId: 'CC-1027', title: 'Restore water supply', department: 'Water Works', priority: 'URGENT', status: 'in_progress', assignedAt: '2d ago' },
  { id: 'WO-089', caseId: 'CC-1019', title: 'Clear garbage accumulation', department: 'Sanitation', priority: 'NORMAL', status: 'completed', assignedAt: '4d ago' },
  { id: 'WO-086', caseId: 'CC-1015', title: 'Unblock drainage', department: 'Drainage', priority: 'LOW', status: 'completed', assignedAt: '7d ago' },
];

const DEPARTMENTS = ['All', 'Road Maintenance', 'Sanitation', 'Electrical', 'Water Works', 'Drainage', 'Garbage Management'];

function PriorityChip({ priority }: { priority: string }) {
  const cls: Record<string, string> = {
    URGENT: 'cc-priority-urgent', HIGH: 'cc-priority-high',
    NORMAL: 'cc-priority-normal', LOW: 'cc-priority-low',
  };
  return <span className={`cc-chip text-[10px] ${cls[priority] ?? ''}`}>{priority}</span>;
}

const columns = [
  { key: 'assigned' as const, label: 'Assigned', tone: 'bg-lime-tint' },
  { key: 'in_progress' as const, label: 'In Progress', tone: 'bg-amber/20' },
  { key: 'completed' as const, label: 'Completed', tone: 'bg-lime/20' },
];

const DepartmentCoordinationPage: React.FC = () => {
  const [deptFilter, setDeptFilter] = useState('All');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState<string | null>(null);

  const selectedWorkOrder = mockWorkOrders.find(wo => wo.id === selectedWorkOrderId);

  const filtered = mockWorkOrders.filter(wo =>
    deptFilter === 'All' || wo.department === deptFilter
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A06</div>
        <h1 className="cc-title cc-headline-pop">Departments</h1>
      </div>

      {/* Filter + Actions */}
      <div className="flex items-center gap-3 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <select
          value={deptFilter}
          onChange={(e) => setDeptFilter(e.target.value)}
          className="px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink font-medium"
          style={{ minHeight: '44px' }}
          aria-label="Filter by department"
        >
          {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <button
          className="cc-btn cc-btn-primary text-sm"
          onClick={() => setShowCreateForm(!showCreateForm)}
        >
          <Plus className="h-4 w-4" /> Create Work Order
        </button>
      </div>

      {/* Create work order form (collapsed by default) */}
      {showCreateForm && (
        <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
          <h3 className="font-display text-sm text-ink mb-4">New Work Order</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono text-muted uppercase">Case ID</label>
              <input
                type="text"
                placeholder="CC-XXXX"
                className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink"
                style={{ minHeight: '44px' }}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono text-muted uppercase">Department</label>
              <select className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink" style={{ minHeight: '44px' }}>
                {DEPARTMENTS.filter(d => d !== 'All').map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-[10px] font-mono text-muted uppercase">Description</label>
              <textarea
                placeholder="Work order description..."
                rows={3}
                className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted resize-none"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button className="cc-btn cc-btn-primary text-sm">
              <Plus className="h-4 w-4" /> Create
            </button>
            <button className="cc-btn cc-btn-outline text-sm" onClick={() => setShowCreateForm(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Three columns: Assigned, In Progress, Completed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {columns.map((col, ci) => {
          const items = filtered.filter(wo => wo.status === col.key);
          return (
            <div key={col.key} className="cc-fade-up" style={{ '--stagger-index': ci + 1 } as React.CSSProperties}>
              <div className={`cc-card overflow-hidden`}>
                {/* Column header */}
                <div className={`px-4 py-3 border-b-2 border-ink ${col.tone}`}>
                  <div className="flex items-center justify-between">
                    <h3 className="font-display text-sm text-ink">{col.label}</h3>
                    <span className="cc-chip text-[9px] py-0 px-1.5">{items.length}</span>
                  </div>
                </div>
                {/* Items */}
                <div className="p-3 space-y-3 min-h-[200px]">
                  {items.length === 0 && (
                    <div className="text-center text-xs font-mono text-muted py-8">
                      No work orders
                    </div>
                  )}
                  {items.map((wo, i) => (
                    <div
                      key={wo.id}
                      className="cc-card p-3 cc-card-lift cc-fade-up cursor-pointer hover:border-wine/50 transition-colors"
                      style={{ '--stagger-index': i } as React.CSSProperties}
                      onClick={() => setSelectedWorkOrderId(wo.id)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-[10px] font-semibold" style={{ color: 'var(--wine)' }}>{wo.id}</span>
                        <PriorityChip priority={wo.priority} />
                      </div>
                      <p className="text-xs text-ink font-medium mb-2 line-clamp-2">{wo.title}</p>
                      <div className="flex items-center justify-between text-[10px] font-mono text-muted">
                        <span className="flex items-center gap-1">
                          <Building2 className="h-3 w-3" /> {wo.department}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {wo.assignedAt}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 mt-2 pt-2 border-t border-dot">
                        <span className="cc-chip text-[9px] py-0 px-1.5 border-muted/30 text-muted">
                          {wo.caseId}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Work Order drawer */}
      {selectedWorkOrder && (
        <>
          <div className="fixed inset-0 bg-ink/20 z-30" onClick={() => setSelectedWorkOrderId(null)} aria-hidden="true" />
          <div className="fixed inset-y-0 right-0 w-96 z-40 cc-card cc-fade-up"
            style={{ borderRadius: 'var(--radius-lg) 0 0 var(--radius-lg)', borderRight: 'none', '--stagger-index': 0 } as React.CSSProperties}
          >
            <div className="h-full overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b-2 border-ink">
                <h3 className="font-display text-lg text-ink">{selectedWorkOrder.id}</h3>
                <button onClick={() => setSelectedWorkOrderId(null)} className="w-8 h-8 rounded-md border-2 border-ink flex items-center justify-center hover:bg-lime-tint" aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <PriorityChip priority={selectedWorkOrder.priority} />
                  <span className={`cc-chip text-[10px] ${columns.find(c => c.key === selectedWorkOrder.status)?.tone}`}>{selectedWorkOrder.status}</span>
                </div>
                <h4 className="font-medium text-ink">{selectedWorkOrder.title}</h4>
                <div className="space-y-3">
                  {[
                    { label: 'Department', value: selectedWorkOrder.department },
                    { label: 'Case ID', value: selectedWorkOrder.caseId },
                    { label: 'Assigned', value: selectedWorkOrder.assignedAt },
                  ].map(f => (
                    <div key={f.label} className="flex justify-between items-center py-2 border-b border-dot">
                      <span className="text-[10px] font-mono text-muted uppercase">{f.label}</span>
                      <span className="text-sm font-semibold text-ink">{f.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default DepartmentCoordinationPage;
