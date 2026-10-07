/**
 * A05 — AI Triage Panel
 * Left: wine recommendation panel with confidence gauge and typed reasons,
 * score bars, duplicate cards. Right: decision form and audit trail.
 *
 * Data: POST /cases/{id}/triage/analyze (reasons, score_breakdown, warnings),
 *       POST /fusion/analyze (signals: semantic, geospatial, temporal, category),
 *       POST /triage/decision. A reason is required when the decision differs
 *       from the advice.
 */
import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Brain, CheckCircle, XCircle, Edit2,
  AlertTriangle, Info, ArrowUpRight,
} from 'lucide-react';
import { useTriageAnalyze, useTriageDecide } from '../hooks/useAdminApi';

const MOCK_ANALYSIS = {
  recommendation: {
    severity: 'HIGH',
    priority: 'URGENT',
    department: 'Road Maintenance',
    sla_hours: 24,
  },
  confidence: 0.88,
  reasons: [
    'Deep pothole (>10 cm) confirmed by image classification model',
    'GPS location matches W12 recurring road-damage cluster (31 reports / 7 days)',
    'Citizen voice report confirms active traffic hazard',
    'No matching resolved work order in 90-day window for this location',
  ],
  score_breakdown: [
    { signal: 'Semantic', score: 0.92 },
    { signal: 'Geospatial', score: 0.87 },
    { signal: 'Temporal', score: 0.85 },
    { signal: 'Category', score: 0.89 },
  ],
  warnings: [
    'Infrastructure report suggests concurrent drainage issue — verify joint ownership with Sanitation dept.',
  ],
};

const DEPARTMENTS = [
  'Road Maintenance', 'Electrical', 'Sanitation',
  'Water Works', 'Garbage Management', 'Public Works',
];
const SEVERITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const PRIORITY_OPTIONS = ['LOW', 'NORMAL', 'HIGH', 'URGENT'];

const AITriagePage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const triageAnalyze = useTriageAnalyze();
  const triageDecide = useTriageDecide();

  const [editing, setEditing] = useState(false);
  const [severity, setSeverity] = useState(MOCK_ANALYSIS.recommendation.severity);
  const [priority, setPriority] = useState(MOCK_ANALYSIS.recommendation.priority);
  const [department, setDepartment] = useState(MOCK_ANALYSIS.recommendation.department);
  const [slaHours, setSlaHours] = useState(String(MOCK_ANALYSIS.recommendation.sla_hours));
  const [reason, setReason] = useState('');

  const isEdited =
    severity !== MOCK_ANALYSIS.recommendation.severity ||
    priority !== MOCK_ANALYSIS.recommendation.priority ||
    department !== MOCK_ANALYSIS.recommendation.department ||
    Number(slaHours) !== MOCK_ANALYSIS.recommendation.sla_hours;

  const handleAccept = () => {
    navigate(`/cases/${caseId}`);
  };
  const handleReject = () => {
    navigate(`/cases/${caseId}`);
  };
  const handleSaveEdit = () => {
    navigate(`/cases/${caseId}`);
  };

  const confPct = Math.round(MOCK_ANALYSIS.confidence * 100);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="cc-page-header">
        <Link to={`/cases/${caseId}`}>
          <button className="cc-btn cc-btn-outline text-xs py-1 px-3 mb-3">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Case
          </button>
        </Link>
        <div className="cc-eyebrow cc-fade-up">A05</div>
        <div className="flex items-center gap-3 mt-1">
          <h1 className="cc-title cc-headline-pop">AI Triage</h1>
          <span className="cc-chip text-xs font-mono" style={{ color: 'var(--wine)' }}>{caseId}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Left: Wine recommendation panel ────────────────────────────── */}
        <div className="space-y-5">
          {/* Recommendation card on wine panel */}
          <div className="cc-ai-panel cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-display text-on-wine flex items-center gap-2">
                <Brain className="h-4 w-4" /> AI Recommendation
              </h3>
              <span className="cc-chip cc-chip-dashed text-[10px] border-on-wine/40 text-on-wine/80">
                AI Generated
              </span>
            </div>

            {/* Confidence gauge */}
            <div className="flex items-center gap-4 mb-5">
              <div
                className="cc-gauge"
                style={{ '--gauge-value': confPct, width: '80px', height: '80px' } as React.CSSProperties}
              >
                <div className="cc-gauge-inner" style={{ background: 'var(--wine)' }}>
                  <span className="font-display text-lg text-on-wine">{confPct}%</span>
                </div>
              </div>
              <div>
                <p className="text-xs font-mono text-on-wine/50 uppercase">Confidence</p>
                <p className="text-sm text-on-wine mt-1">
                  {confPct >= 80 ? 'High confidence recommendation' : 'Review recommended'}
                </p>
              </div>
            </div>

            {/* Recommendation fields */}
            <div className="grid grid-cols-2 gap-3 text-xs mb-4">
              {[
                { label: 'Severity', value: MOCK_ANALYSIS.recommendation.severity },
                { label: 'Priority', value: MOCK_ANALYSIS.recommendation.priority },
                { label: 'Department', value: MOCK_ANALYSIS.recommendation.department },
                { label: 'SLA', value: `${MOCK_ANALYSIS.recommendation.sla_hours}h` },
              ].map(({ label, value }) => (
                <div key={label} className="bg-rust-deep/30 rounded-md p-2.5 border border-on-wine/10">
                  <p className="text-on-wine/50 text-[10px] font-mono uppercase mb-0.5">{label}</p>
                  <p className="font-semibold text-on-wine">{value}</p>
                </div>
              ))}
            </div>

            {/* Typed AI reasons */}
            <p className="text-xs font-display text-on-wine/60 mb-2">Evidence-backed reasoning:</p>
            <ul className="space-y-1.5">
              {MOCK_ANALYSIS.reasons.map((r, i) => (
                <li key={i} className="cc-typed-line text-xs text-on-wine/70 flex gap-2" style={{ '--line-index': i } as React.CSSProperties}>
                  <CheckCircle className="h-3.5 w-3.5 text-lime flex-shrink-0 mt-0.5" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>

            <p className="text-[10px] text-on-wine/40 mt-4 font-mono flex items-center gap-1">
              <Info className="h-3 w-3" />
              AI recommendations are advisory only. Admin decision is final and audited.
            </p>
          </div>

          {/* Score breakdown bars */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-4">Score Breakdown</h3>
            <div className="space-y-3">
              {MOCK_ANALYSIS.score_breakdown.map((signal, i) => (
                <div key={signal.signal}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-muted">{signal.signal}</span>
                    <span className="text-xs font-semibold text-ink">{(signal.score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="cc-meter">
                    <div
                      className="cc-meter-fill cc-meter-fill-lime cc-bar-grow-x"
                      style={{
                        width: `${signal.score * 100}%`,
                        '--stagger-index': i,
                      } as React.CSSProperties}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Warnings */}
          {MOCK_ANALYSIS.warnings.length > 0 && (
            <div className="cc-banner-degraded cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <div>
                <p className="text-xs font-semibold mb-1">Warnings</p>
                {MOCK_ANALYSIS.warnings.map((w, i) => (
                  <p key={i} className="text-xs">{w}</p>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Right: Decision form ───────────────────────────────────────── */}
        <div className="space-y-5">
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-sm font-display text-ink">Triage Decision</h3>
              <button
                className="cc-btn cc-btn-outline text-xs py-1 px-3"
                onClick={() => setEditing(!editing)}
              >
                <Edit2 className="h-3.5 w-3.5" />
                {editing ? 'Lock fields' : 'Edit recommendation'}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-5">
              {/* Severity */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono text-muted uppercase">Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  disabled={!editing}
                  className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink disabled:opacity-50"
                  style={{ minHeight: '44px' }}
                >
                  {SEVERITY_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              {/* Priority */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono text-muted uppercase">Priority</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  disabled={!editing}
                  className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink disabled:opacity-50"
                  style={{ minHeight: '44px' }}
                >
                  {PRIORITY_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              {/* Department */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono text-muted uppercase">Department</label>
                <select
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  disabled={!editing}
                  className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink disabled:opacity-50"
                  style={{ minHeight: '44px' }}
                >
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>

              {/* SLA */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono text-muted uppercase">SLA (hours)</label>
                <select
                  value={slaHours}
                  onChange={(e) => setSlaHours(e.target.value)}
                  disabled={!editing}
                  className="w-full px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink disabled:opacity-50"
                  style={{ minHeight: '44px' }}
                >
                  {['4','8','12','24','48','72','168'].map(h => <option key={h} value={h}>{h}h</option>)}
                </select>
              </div>
            </div>

            {/* Reason / justification */}
            <div className="space-y-1.5 mb-5">
              <label className="text-[10px] font-mono text-muted uppercase">
                Decision justification {isEdited && <span className="text-fire">*required when editing</span>}
              </label>
              <textarea
                placeholder="Enter reason for your decision (required when overriding AI recommendation)..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                className="w-full p-3 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted resize-none"
                style={{ minHeight: '44px' }}
              />
            </div>

            {/* Action buttons */}
            <div className="flex gap-3">
              <button
                className="cc-btn cc-btn-primary flex-1 justify-center"
                onClick={isEdited ? handleSaveEdit : handleAccept}
                disabled={isEdited && !reason.trim()}
              >
                <CheckCircle className="h-4 w-4" />
                {isEdited ? 'Save Edited Decision' : 'Accept AI Recommendation'}
              </button>
              <button
                className="cc-btn cc-btn-outline"
                onClick={handleReject}
                style={{ borderColor: 'var(--fire)', color: 'var(--fire)' }}
              >
                <XCircle className="h-4 w-4" /> Reject
              </button>
            </div>

            {isEdited && (
              <p className="text-xs text-amber mt-3 flex items-center gap-1 font-mono">
                <AlertTriangle className="h-3.5 w-3.5" />
                You have modified the AI recommendation. A justification is required and will be audited.
              </p>
            )}
          </div>

          {/* RULES ONLY chip when warnings indicate it */}
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
            <h3 className="text-sm font-display text-ink mb-3">Decision Mode</h3>
            <div className="flex items-center gap-3">
              {/* Solid chip for rules/human decisions */}
              <span className="cc-chip text-[11px] bg-lime-tint">RULES + AI</span>
              <span className="text-xs text-muted">Both deterministic rules and AI model contributed to this recommendation.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AITriagePage;
