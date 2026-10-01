/**
 * A05 — AI Triage Panel
 * Displays AI recommendation for a case.
 * Admin can accept, edit, or reject. All overrides are audited.
 * 
 * Data: useTriageAnalyze() → POST /cases/:caseId/triage/analyze
 *       useTriageDecide()   → POST /cases/:caseId/triage/decision
 */
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Brain, CheckCircle, XCircle, Edit2,
  AlertTriangle, Loader2, Info, ChevronDown
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useTriageAnalyze, useTriageDecide } from '../hooks/useAdminApi';

// Mock AI analysis — replaced by real API call
const MOCK_ANALYSIS = {
  recommendation: {
    severity:    'HIGH',
    priority:    'URGENT',
    department:  'Road Maintenance',
    sla_hours:   24,
  },
  confidence: 0.88,
  reasons: [
    'Deep pothole (>10 cm) confirmed by image classification model',
    'GPS location matches W12 recurring road-damage cluster (31 reports / 7 days)',
    'Citizen voice report confirms active traffic hazard',
    'No matching resolved work order in 90-day window for this location',
  ],
  warnings: [
    'Infrastructure report suggests concurrent drainage issue — verify joint ownership with Sanitation dept.',
  ],
};

const DEPARTMENTS = [
  'Road Maintenance',
  'Electrical',
  'Sanitation',
  'Water Works',
  'Garbage Management',
  'Public Works',
];

const SEVERITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const PRIORITY_OPTIONS  = ['LOW', 'NORMAL', 'HIGH', 'URGENT', 'CRITICAL'];

// ─── Component ────────────────────────────────────────────────────────────────

const AITriagePage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate  = useNavigate();

  // Real hooks — currently mock fires since backend isn't connected
  const triageAnalyze = useTriageAnalyze();
  const triageDecide  = useTriageDecide();

  // Decision form state (pre-filled from AI recommendation)
  const [editing,    setEditing]    = useState(false);
  const [severity,   setSeverity]   = useState(MOCK_ANALYSIS.recommendation.severity);
  const [priority,   setPriority]   = useState(MOCK_ANALYSIS.recommendation.priority);
  const [department, setDepartment] = useState(MOCK_ANALYSIS.recommendation.department);
  const [slaHours,   setSlaHours]   = useState(String(MOCK_ANALYSIS.recommendation.sla_hours));
  const [reason,     setReason]     = useState('');
  const [decision,   setDecision]   = useState<'accepted' | 'edited' | 'rejected' | null>(null);

  // Detect if form was edited vs accepted as-is
  const isEdited =
    severity   !== MOCK_ANALYSIS.recommendation.severity   ||
    priority   !== MOCK_ANALYSIS.recommendation.priority   ||
    department !== MOCK_ANALYSIS.recommendation.department ||
    Number(slaHours) !== MOCK_ANALYSIS.recommendation.sla_hours;

  const handleAccept = async () => {
    setDecision('accepted');
    // TODO: await triageDecide.mutateAsync({ caseId: caseId!, body: { severity, priority, department_id: department, sla_hours: Number(slaHours), reason: reason || 'Accepted AI recommendation' } });
    navigate(`/cases/${caseId}`);
  };

  const handleReject = () => {
    setDecision('rejected');
    // Rejection requires a reason — navigate back after logging
    navigate(`/cases/${caseId}`);
  };

  const handleSaveEdit = async () => {
    setDecision('edited');
    // TODO: await triageDecide.mutateAsync(...)
    navigate(`/cases/${caseId}`);
  };

  const confPct = Math.round(MOCK_ANALYSIS.confidence * 100);
  const confColor = confPct >= 80 ? 'bg-green-500' : confPct >= 60 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="p-6 bg-civic-bg min-h-screen space-y-6 max-w-4xl">

      {/* Back + header */}
      <div>
        <Button variant="ghost" size="sm" asChild className="mb-2 -ml-2">
          <Link to={`/cases/${caseId}`}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Case
          </Link>
        </Button>
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-purple-600 flex items-center justify-center">
            <Brain className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">AI Triage Panel</h2>
            <p className="text-sm text-gray-500">Case <span className="font-mono text-green-700">{caseId}</span></p>
          </div>
        </div>
      </div>

      {/* AI Recommendation */}
      <div className="civic-card p-6 rounded-xl border border-purple-100 bg-purple-50/30 space-y-5">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-800 flex items-center gap-2">
            <Brain className="h-4 w-4 text-purple-600" />
            AI Recommendation
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Confidence</span>
            <span className={`text-xs font-bold ${confPct >= 80 ? 'text-green-700' : 'text-yellow-700'}`}>{confPct}%</span>
          </div>
        </div>

        {/* Confidence bar */}
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div className={`${confColor} h-2 rounded-full transition-all`} style={{ width: `${confPct}%` }} />
        </div>

        {/* Recommendation fields */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          {[
            { label: 'Category',   value: 'Road Damage' },
            { label: 'Subcategory',value: 'Pothole' },
            { label: 'Severity',   value: MOCK_ANALYSIS.recommendation.severity },
            { label: 'Priority',   value: MOCK_ANALYSIS.recommendation.priority },
            { label: 'Department', value: MOCK_ANALYSIS.recommendation.department },
            { label: 'SLA',        value: `${MOCK_ANALYSIS.recommendation.sla_hours} hours` },
          ].map(({ label, value }) => (
            <div key={label} className="flex flex-col bg-white rounded-lg p-3 border border-purple-100">
              <span className="text-[10px] text-gray-400 uppercase tracking-wide mb-0.5">{label}</span>
              <span className="font-semibold text-gray-800">{value}</span>
            </div>
          ))}
        </div>

        {/* Reasons */}
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-2">Evidence-backed reasoning</p>
          <ul className="space-y-1.5">
            {MOCK_ANALYSIS.reasons.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                <CheckCircle className="h-3.5 w-3.5 text-green-500 flex-shrink-0 mt-0.5" />
                {r}
              </li>
            ))}
          </ul>
        </div>

        {/* Warnings */}
        {MOCK_ANALYSIS.warnings.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-amber-800 mb-1 flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5" /> Warnings
            </p>
            {MOCK_ANALYSIS.warnings.map((w, i) => (
              <p key={i} className="text-xs text-amber-700">{w}</p>
            ))}
          </div>
        )}

        <p className="text-[10px] text-gray-400 italic flex items-center gap-1">
          <Info className="h-3 w-3" />
          AI recommendations are advisory only. Authorized admin decision is final and audited.
        </p>
      </div>

      {/* Decision form */}
      <div className="civic-card p-6 rounded-xl border border-gray-100 space-y-5">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">Triage Decision</h3>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditing(!editing)}
            className="text-xs"
          >
            <Edit2 className="h-3.5 w-3.5 mr-1.5" />
            {editing ? 'Lock fields' : 'Edit recommendation'}
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {/* Severity */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600">Severity</label>
            <Select value={severity} onValueChange={setSeverity} disabled={!editing}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {SEVERITY_OPTIONS.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {/* Priority */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600">Priority</label>
            <Select value={priority} onValueChange={setPriority} disabled={!editing}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {PRIORITY_OPTIONS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {/* Department */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600">Department</label>
            <Select value={department} onValueChange={setDepartment} disabled={!editing}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {DEPARTMENTS.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {/* SLA */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600">SLA (hours)</label>
            <Select value={slaHours} onValueChange={setSlaHours} disabled={!editing}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {['4','8','12','24','48','72','168'].map(h => (
                  <SelectItem key={h} value={h}>{h}h</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Reason / justification */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-gray-600">
            Decision justification {isEdited && <span className="text-red-500">*required when editing</span>}
          </label>
          <Textarea
            placeholder="Enter reason for your decision (required when overriding AI recommendation)…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="text-sm"
          />
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 pt-2">
          <Button
            className="flex-1 bg-green-600 hover:bg-green-700 text-white"
            onClick={isEdited ? handleSaveEdit : handleAccept}
            disabled={isEdited && !reason.trim()}
          >
            <CheckCircle className="h-4 w-4 mr-1.5" />
            {isEdited ? 'Save Edited Decision' : 'Accept AI Recommendation'}
          </Button>
          <Button
            variant="outline"
            className="text-red-600 border-red-200 hover:bg-red-50"
            onClick={handleReject}
          >
            <XCircle className="h-4 w-4 mr-1.5" />
            Reject
          </Button>
        </div>

        {isEdited && (
          <p className="text-xs text-amber-600 flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5" />
            You have modified the AI recommendation. A justification is required and will be audited.
          </p>
        )}
      </div>
    </div>
  );
};

export default AITriagePage;
