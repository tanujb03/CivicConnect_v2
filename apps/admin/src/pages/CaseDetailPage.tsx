/**
 * A04 — Case Detail / Evidence
 * Header with chips, four stat cards, evidence grid, classification panel,
 * work order, verification card, timeline column, notes.
 *
 * Data: GET /cases/{id}, GET /cases/{id}/timeline, GET /evidence/{id} for
 * short-lived signed URLs.
 * Actions: POST /cases/{id}/reject (reason required), work order, triage.
 * Gap: internal notes (POST /cases/{id}/notes).
 */
import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Brain, Camera, MapPin, Clock, User,
  FileText, AlertTriangle, CheckCircle2, MessageSquare,
  GitMerge, Loader2, ExternalLink, Plus, ArrowUpRight,
} from 'lucide-react';
import { useCase, useCaseTimeline, usePatchCase } from '../hooks/useAdminApi';

// ─── Mock evidence + related cases until media API is wired ─────────────────
const mockEvidence = [
  { id: 'e1', type: 'IMAGE', label: 'Citizen photo 1' },
  { id: 'e2', type: 'IMAGE', label: 'Citizen photo 2' },
  { id: 'e3', type: 'AUDIO', label: 'Voice report' },
  { id: 'e4', type: 'IMAGE', label: 'Field verification' },
];

const mockRelated = [
  { id: 'CC-1039', title: 'Pothole — adjacent block', similarity: 0.91 },
  { id: 'CC-1027', title: 'Road damage near school', similarity: 0.76 },
];

const mockAiClassification = {
  category: 'Road Damage',
  subcategory: 'Pothole',
  severity: 'HIGH',
  priority: 'URGENT',
  department: 'Road Maintenance',
  sla_hours: 24,
  confidence: 0.88,
  reasons: [
    'Image shows exposed subgrade consistent with deep pothole (>10 cm)',
    'GPS location matches W12 recurring road-damage cluster',
    'Citizen voice report confirms traffic hazard',
  ],
};

// ─── Priority chip ─────────────────────────────────────────────────────────
function PriorityChip({ priority }: { priority: string }) {
  const cls: Record<string, string> = {
    URGENT: 'cc-priority-urgent', HIGH: 'cc-priority-high',
    NORMAL: 'cc-priority-normal', LOW: 'cc-priority-low',
  };
  return <span className={`cc-chip text-[11px] ${cls[priority] ?? 'cc-priority-normal'}`}>{priority}</span>;
}

function StatusChip({ status }: { status: string }) {
  const labels: Record<string, string> = {
    SUBMITTED: 'Submitted', TRIAGED: 'Triaged', ASSIGNED: 'Assigned',
    IN_PROGRESS: 'In Progress', RESOLVED: 'Resolved', CLOSED: 'Closed', REOPENED: 'Reopened',
  };
  return <span className="cc-chip text-[11px]">{labels[status] ?? status}</span>;
}

// ─── Page ─────────────────────────────────────────────────────────────────────
const CaseDetailPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { data: caseData, isLoading, isError } = useCase(caseId);
  const { data: timeline } = useCaseTimeline(caseId);
  const patchCase = usePatchCase();
  const [note, setNote] = useState('');

  // ── Loading state ─────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex items-center gap-3 py-12 justify-center text-muted">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="font-mono text-sm">Loading case...</span>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────
  if (isError || !caseData) {
    return (
      <div className="space-y-4 py-8">
        <div className="cc-banner-error">
          Could not load case. It may not exist or the backend is not yet connected.
        </div>
        <button className="cc-btn cc-btn-outline" onClick={() => navigate('/cases')}>
          <ArrowLeft className="h-4 w-4" /> Back to Cases
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="cc-page-header">
        <button
          className="cc-btn cc-btn-outline text-xs py-1 px-3 mb-3"
          onClick={() => navigate('/cases')}
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Cases
        </button>
        <div className="cc-eyebrow cc-fade-up">A04</div>
        <div className="flex items-center gap-3 flex-wrap mt-1">
          <h1 className="cc-title cc-headline-pop">{caseData.case_number}</h1>
          <StatusChip status={caseData.status} />
          <PriorityChip priority={caseData.priority ?? 'NORMAL'} />
        </div>
        <p className="text-sm text-muted mt-2">{caseData.title ?? 'Untitled case'}</p>
      </div>

      {/* ── Action buttons ───────────────────────────────────────────────── */}
      <div className="flex gap-2 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <Link to={`/cases/${caseId}/triage`}>
          <button className="cc-btn cc-btn-dark text-sm">
            <Brain className="h-4 w-4" /> AI Triage
          </button>
        </Link>
        <button className="cc-btn cc-btn-outline text-sm">
          <Plus className="h-4 w-4" /> Work Order
        </button>
      </div>

      {/* ── Four stat cards ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Department', value: caseData.department_id ?? 'Unassigned', icon: User },
          { label: 'Ward', value: caseData.ward_id ?? '---', icon: MapPin },
          { label: 'Category', value: caseData.category ?? '---', icon: FileText },
          { label: 'Created', value: new Date(caseData.created_at).toLocaleDateString('en-IN'), icon: Clock },
        ].map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="cc-card p-4 cc-card-lift cc-fade-up" style={{ '--stagger-index': i + 1 } as React.CSSProperties}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
                  <Icon className="h-3.5 w-3.5 text-ink" />
                </div>
                <span className="text-[10px] font-mono text-muted uppercase">{stat.label}</span>
              </div>
              <p className="text-sm font-semibold text-ink">{stat.value}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left column: citizen input + evidence + AI classification ─── */}
        <div className="lg:col-span-2 space-y-5">
          {/* Citizen Report */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 5 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3 flex items-center gap-2">
              <FileText className="h-4 w-4" style={{ color: 'var(--wine)' }} /> Citizen Report
            </h3>
            <p className="text-sm text-ink leading-relaxed">
              {caseData.description ?? 'No description provided.'}
            </p>
            <div className="flex flex-wrap gap-4 mt-4 text-xs font-mono text-muted">
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {caseData.location.latitude.toFixed(4)}, {caseData.location.longitude.toFixed(4)}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                Submitted {new Date(caseData.created_at).toLocaleString('en-IN')}
              </span>
            </div>
          </div>

          {/* Evidence grid */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 6 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3 flex items-center gap-2">
              <Camera className="h-4 w-4" style={{ color: 'var(--wine)' }} />
              Evidence ({mockEvidence.length} items)
            </h3>
            <div className="grid grid-cols-4 gap-3">
              {mockEvidence.map((ev) => (
                <div
                  key={ev.id}
                  className="bg-ground border-2 border-dot rounded-md aspect-square flex flex-col items-center justify-center gap-1 text-muted hover:bg-lime-tint cursor-pointer transition-colors cc-card-lift"
                >
                  <Camera className="h-6 w-6" />
                  <span className="text-[10px] text-center px-1 font-mono">{ev.label}</span>
                  <span className="cc-chip text-[9px] py-0 px-1.5 border-muted/40">{ev.type}</span>
                </div>
              ))}
            </div>
            <p className="text-xs font-mono text-muted mt-3">
              Media served via signed URLs when evidence API is connected.
            </p>
          </div>

          {/* AI Classification — wine panel since this is AI-generated content */}
          <div className="cc-ai-panel cc-fade-up" style={{ '--stagger-index': 7 } as React.CSSProperties}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-display text-on-wine flex items-center gap-2">
                <Brain className="h-4 w-4" /> AI Classification
              </h3>
              <span className="cc-chip cc-chip-dashed text-[10px] border-on-wine/40 text-on-wine/80">
                {(mockAiClassification.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
            {/* Confidence meter */}
            <div className="cc-meter mb-4" style={{ background: 'var(--rust-deep)', borderColor: 'var(--on-wine)/30' }}>
              <div
                className="cc-meter-fill cc-bar-grow-x"
                style={{
                  width: `${mockAiClassification.confidence * 100}%`,
                  background: 'var(--lime)',
                }}
              />
            </div>
            <div className="grid grid-cols-3 gap-3 text-xs mb-4">
              {[
                { label: 'Category', value: mockAiClassification.category },
                { label: 'Subcategory', value: mockAiClassification.subcategory },
                { label: 'Severity', value: mockAiClassification.severity },
                { label: 'Priority', value: mockAiClassification.priority },
                { label: 'Department', value: mockAiClassification.department },
                { label: 'SLA', value: `${mockAiClassification.sla_hours}h` },
              ].map(({ label, value }) => (
                <div key={label} className="bg-rust-deep/30 rounded-md p-2.5 border border-on-wine/10">
                  <p className="text-on-wine/50 text-[10px] font-mono uppercase mb-0.5">{label}</p>
                  <p className="font-semibold text-on-wine">{value}</p>
                </div>
              ))}
            </div>
            <p className="text-xs font-display text-on-wine/60 mb-2">AI Reasoning:</p>
            <ul className="space-y-1.5">
              {mockAiClassification.reasons.map((r, i) => (
                <li key={i} className="text-xs text-on-wine/70 flex gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-lime flex-shrink-0 mt-0.5" />
                  {r}
                </li>
              ))}
            </ul>
            <p className="text-[10px] text-on-wine/40 mt-3 font-mono">
              AI recommendations are editable. All overrides are audited.
            </p>
          </div>

          {/* Related / Duplicate Cases */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 8 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3 flex items-center gap-2">
              <GitMerge className="h-4 w-4" style={{ color: 'var(--wine)' }} /> Related / Duplicate Cases
            </h3>
            <div className="space-y-2">
              {mockRelated.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-3 bg-ground rounded-md border-2 border-dot">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold" style={{ color: 'var(--wine)' }}>{r.id}</span>
                    <span className="text-xs text-ink">{r.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="cc-chip text-[9px] py-0 px-1.5">{(r.similarity * 100).toFixed(0)}% match</span>
                    <Link to={`/cases/${r.id}`}>
                      <ExternalLink className="h-3.5 w-3.5 text-muted hover:text-ink transition-colors" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
            <button className="cc-btn cc-btn-outline text-xs mt-3">
              <GitMerge className="h-3.5 w-3.5" /> Run Fusion Analysis
            </button>
          </div>

          {/* Internal notes — Gap: POST /cases/{id}/notes not available */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 9 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3 flex items-center gap-2">
              <MessageSquare className="h-4 w-4" style={{ color: 'var(--wine)' }} /> Internal Notes
            </h3>
            <div className="cc-banner-needs-backend mb-3 text-xs">
              Internal notes need a backend endpoint (POST /cases/{'{id}'}/notes). UI-only for now.
            </div>
            <div className="bg-ground rounded-md p-3 text-xs text-ink border-2 border-dot mb-3">
              <span className="font-semibold">Admin Kumar</span>
              <span className="text-muted ml-2 font-mono">2 hours ago</span>
              <p className="mt-1 text-muted">Assigned to road department for immediate attention.</p>
            </div>
            <textarea
              placeholder="Add internal note (not visible to citizen)..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              className="w-full p-3 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted resize-none"
              style={{ minHeight: '44px' }}
            />
            <button
              className="cc-btn cc-btn-primary text-xs mt-2"
              disabled={!note.trim()}
            >
              Add Note
            </button>
          </div>
        </div>

        {/* ── Right column: timeline + assignment + resolution ─────────── */}
        <div className="lg:col-span-1 space-y-5">
          {/* Timeline */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 5 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-4 flex items-center gap-2">
              <Clock className="h-4 w-4" style={{ color: 'var(--wine)' }} /> Case Timeline
            </h3>
            <div className="cc-timeline">
              {(timeline && timeline.items.length > 0
                ? timeline.items.map((ev) => ({
                    event: ev.event_type.replace(/_/g, ' '),
                    time: ev.timestamp,
                    tone: 'surface' as const,
                  }))
                : [
                    { event: 'CASE SUBMITTED', time: caseData.created_at, tone: 'lime' as const },
                    { event: 'TRIAGE ASSIGNED', time: caseData.updated_at, tone: 'wine' as const },
                    { event: 'DEPARTMENT ROUTED', time: caseData.updated_at, tone: 'surface' as const },
                  ]
              ).map((ev, i) => (
                <div
                  key={i}
                  className={`cc-timeline-event cc-fade-up ${
                    ev.tone === 'wine' ? 'cc-timeline-event-wine' :
                    ev.tone === 'lime' ? 'cc-timeline-event-lime' : ''
                  }`}
                  style={{ '--stagger-index': i } as React.CSSProperties}
                >
                  <p className="text-xs font-semibold text-ink">{ev.event}</p>
                  <p className="text-[10px] font-mono text-muted">{new Date(ev.time).toLocaleString('en-IN')}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Assignment */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 6 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3 flex items-center gap-2">
              <User className="h-4 w-4" style={{ color: 'var(--wine)' }} /> Assignment
            </h3>
            <div className="space-y-2">
              {[
                { label: 'Department', value: caseData.department_id ?? 'Unassigned' },
                { label: 'Ward', value: caseData.ward_id ?? '---' },
                { label: 'Priority', value: caseData.priority },
                { label: 'Category', value: caseData.category ?? '---' },
              ].map((row) => (
                <div key={row.label} className="flex justify-between items-center py-2 border-b border-dot">
                  <span className="text-[10px] font-mono text-muted uppercase">{row.label}</span>
                  <span className="text-xs font-semibold text-ink">{row.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Resolution evidence */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 7 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" style={{ color: 'var(--wine)' }} /> Resolution Evidence
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {[1, 2].map((i) => (
                <div key={i} className="bg-ground border-2 border-dashed border-dot rounded-md aspect-video flex flex-col items-center justify-center text-muted">
                  <Camera className="h-5 w-5" />
                  <span className="text-[10px] mt-1 font-mono">Field photo {i}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] font-mono text-muted mt-2">
              Uploaded by field worker after work order completion.
            </p>
          </div>

          {/* Citizen verification */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 8 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" style={{ color: 'var(--amber)' }} /> Citizen Verification
            </h3>
            <p className="text-xs text-muted font-mono">
              Verification pending. Citizen will be notified when resolution evidence is submitted.
              Request verification is automatic when work completes — no button in v1.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CaseDetailPage;
