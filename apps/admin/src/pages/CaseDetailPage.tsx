/**
 * A04 — Case Detail / Evidence
 * Displays: citizen input, media, AI classification, confidence, related cases,
 * duplicate reasoning, priority reasoning, timeline, department, work order,
 * resolution evidence, citizen verification.
 *
 * Data: useCase() + useCaseTimeline() hooks → /cases/:caseId
 */
import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Brain, Camera, MapPin, Clock, User,
  FileText, AlertTriangle, CheckCircle2, MessageSquare,
  GitMerge, Loader2, ExternalLink, Plus,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { useCase, useCaseTimeline, usePatchCase } from '../hooks/useAdminApi';

// ─── Mock evidence + related cases until media API is wired ─────────────────

const mockEvidence = [
  { id: 'e1', type: 'IMAGE',  label: 'Citizen photo 1',   thumb: null },
  { id: 'e2', type: 'IMAGE',  label: 'Citizen photo 2',   thumb: null },
  { id: 'e3', type: 'AUDIO',  label: 'Voice report',       thumb: null },
  { id: 'e4', type: 'IMAGE',  label: 'Field verification', thumb: null },
];

const mockRelated = [
  { id: 'CC-1039', title: 'Pothole — adjacent block', similarity: 0.91 },
  { id: 'CC-1027', title: 'Road damage near school',  similarity: 0.76 },
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

// ─── Helpers ─────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    SUBMITTED:   'bg-blue-100 text-blue-800',
    TRIAGED:     'bg-purple-100 text-purple-800',
    ASSIGNED:    'bg-yellow-100 text-yellow-800',
    IN_PROGRESS: 'bg-orange-100 text-orange-800',
    RESOLVED:    'bg-green-100 text-green-800',
    CLOSED:      'bg-gray-100 text-gray-600',
    REOPENED:    'bg-red-100 text-red-800',
  };
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${map[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    CRITICAL: 'bg-red-100 text-red-800',
    HIGH:     'bg-orange-100 text-orange-800',
    MEDIUM:   'bg-yellow-100 text-yellow-800',
    LOW:      'bg-green-100 text-green-800',
  };
  return <span className={`px-2 py-0.5 rounded text-xs font-semibold ${map[severity] ?? 'bg-gray-100 text-gray-700'}`}>{severity}</span>;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const CaseDetailPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const { data: caseData, isLoading, isError } = useCase(caseId);
  const { data: timeline } = useCaseTimeline(caseId);
  const patchCase = usePatchCase();

  const [note, setNote] = useState('');

  // ── Loading / Error states ─────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="p-8 flex items-center gap-3 text-gray-400">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading case…
      </div>
    );
  }

  if (isError || !caseData) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Could not load case. It may not exist or the backend is not yet connected.
        </div>
        <Button variant="outline" className="mt-4" onClick={() => navigate('/cases')}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Cases
        </Button>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 bg-civic-bg min-h-screen space-y-6">

      {/* Back + header */}
      <div className="flex items-start justify-between">
        <div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/cases')} className="mb-2 -ml-2">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Cases
          </Button>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-bold text-gray-900">
              {caseData.case_number}
            </h2>
            <StatusBadge status={caseData.status} />
            <SeverityBadge severity={caseData.severity ?? 'MEDIUM'} />
          </div>
          <p className="text-gray-600 text-sm mt-1">{caseData.title ?? 'Untitled case'}</p>
        </div>

        <div className="flex gap-2 flex-shrink-0">
          <Link to={`/cases/${caseId}/triage`}>
            <Button size="sm" className="bg-purple-600 hover:bg-purple-700 text-white">
              <Brain className="h-4 w-4 mr-1.5" /> AI Triage
            </Button>
          </Link>
          <Button size="sm" variant="outline">
            <Plus className="h-4 w-4 mr-1.5" /> Work Order
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">

        {/* ── Left column: citizen input + evidence ─────────────────────── */}
        <div className="col-span-2 space-y-5">

          {/* Description */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <FileText className="h-4 w-4 text-green-600" /> Citizen Report
            </h3>
            <p className="text-sm text-gray-700 leading-relaxed">
              {caseData.description ?? 'No description provided.'}
            </p>
            <div className="flex flex-wrap gap-4 mt-4 text-xs text-gray-500">
              <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> {caseData.location.latitude.toFixed(4)}, {caseData.location.longitude.toFixed(4)}</span>
              <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> Submitted {new Date(caseData.created_at).toLocaleString('en-IN')}</span>
              <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> Updated {new Date(caseData.updated_at).toLocaleString('en-IN')}</span>
            </div>
          </div>

          {/* Evidence grid */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Camera className="h-4 w-4 text-green-600" /> Evidence ({mockEvidence.length} items)
            </h3>
            <div className="grid grid-cols-4 gap-3">
              {mockEvidence.map((ev) => (
                <div
                  key={ev.id}
                  className="bg-gray-100 rounded-lg aspect-square flex flex-col items-center justify-center gap-1 text-gray-400 hover:bg-gray-200 cursor-pointer transition-colors"
                >
                  <Camera className="h-6 w-6" />
                  <span className="text-[10px] text-center px-1">{ev.label}</span>
                  <Badge variant="secondary" className="text-[9px] py-0">{ev.type}</Badge>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-3 italic">
              Media bytes served via signed URLs when backend evidence API is connected.
            </p>
          </div>

          {/* AI Classification */}
          <div className="civic-card p-5 rounded-xl border border-purple-100 bg-purple-50/30">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Brain className="h-4 w-4 text-purple-600" /> AI Classification
              <span className="ml-auto text-xs text-gray-400">Confidence: {(mockAiClassification.confidence * 100).toFixed(0)}%</span>
            </h3>
            <div className="w-full bg-gray-200 rounded-full h-1.5 mb-4">
              <div
                className="bg-purple-500 h-1.5 rounded-full"
                style={{ width: `${mockAiClassification.confidence * 100}%` }}
              />
            </div>
            <div className="grid grid-cols-3 gap-3 text-xs mb-4">
              {[
                { label: 'Category',    value: mockAiClassification.category },
                { label: 'Subcategory', value: mockAiClassification.subcategory },
                { label: 'Severity',    value: mockAiClassification.severity },
                { label: 'Priority',    value: mockAiClassification.priority },
                { label: 'Department',  value: mockAiClassification.department },
                { label: 'SLA',         value: `${mockAiClassification.sla_hours}h` },
              ].map(({ label, value }) => (
                <div key={label} className="bg-white rounded-lg p-2.5 border border-purple-100">
                  <p className="text-gray-400 text-[10px] mb-0.5">{label}</p>
                  <p className="font-semibold text-gray-800">{value}</p>
                </div>
              ))}
            </div>
            <p className="text-xs font-medium text-gray-600 mb-1">AI reasoning:</p>
            <ul className="space-y-1">
              {mockAiClassification.reasons.map((r, i) => (
                <li key={i} className="text-xs text-gray-600 flex gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-purple-400 flex-shrink-0 mt-0.5" />
                  {r}
                </li>
              ))}
            </ul>
            <p className="text-[10px] text-gray-400 mt-3 italic">
              AI recommendations are editable. All overrides are audited.
            </p>
          </div>

          {/* Related / Duplicate Cases */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <GitMerge className="h-4 w-4 text-green-600" /> Related / Duplicate Cases
            </h3>
            <div className="space-y-2">
              {mockRelated.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-green-700">{r.id}</span>
                    <span className="text-xs text-gray-600">{r.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">
                      {(r.similarity * 100).toFixed(0)}% match
                    </span>
                    <Link to={`/cases/${r.id}`}>
                      <ExternalLink className="h-3.5 w-3.5 text-gray-400 hover:text-green-600" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
            <Button size="sm" variant="outline" className="mt-3 text-xs">
              <GitMerge className="h-3.5 w-3.5 mr-1.5" /> Run Fusion Analysis
            </Button>
          </div>

          {/* Internal notes */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-green-600" /> Internal Notes
            </h3>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 mb-3">
              <span className="font-medium">Admin Kumar</span> · 2 hours ago
              <p className="mt-1 text-gray-500">Assigned to road department for immediate attention.</p>
            </div>
            <Textarea
              placeholder="Add internal note (not visible to citizen)…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              className="text-sm"
            />
            <Button size="sm" className="mt-2 bg-green-600 hover:bg-green-700 text-white" disabled={!note.trim()}>
              Add Note
            </Button>
          </div>
        </div>

        {/* ── Right column: timeline + assignment ───────────────────────── */}
        <div className="col-span-1 space-y-5">

          {/* Timeline */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
              <Clock className="h-4 w-4 text-green-600" /> Case Timeline
            </h3>
            {timeline && timeline.items.length > 0 ? (
              <ol className="relative border-l border-gray-200 space-y-4 ml-3">
                {timeline.items.map((ev) => (
                  <li key={ev.id} className="ml-4">
                    <div className="absolute -left-1.5 w-3 h-3 bg-green-500 rounded-full mt-1" />
                    <p className="text-xs font-semibold text-gray-700">{ev.event_type.replace(/_/g, ' ')}</p>
                    <p className="text-[10px] text-gray-400">{new Date(ev.timestamp).toLocaleString('en-IN')}</p>
                  </li>
                ))}
              </ol>
            ) : (
              /* Fallback mock timeline */
              <ol className="relative border-l border-gray-200 space-y-4 ml-3">
                {[
                  { event: 'CASE SUBMITTED',   time: caseData.created_at,  actor: 'Citizen' },
                  { event: 'TRIAGE ASSIGNED',   time: caseData.updated_at,  actor: 'AI System' },
                  { event: 'DEPARTMENT ROUTED', time: caseData.updated_at,  actor: 'Admin Kumar' },
                ].map((ev, i) => (
                  <li key={i} className="ml-4">
                    <div className="absolute -left-1.5 w-3 h-3 bg-green-500 rounded-full mt-1" />
                    <p className="text-xs font-semibold text-gray-700">{ev.event}</p>
                    <p className="text-[10px] text-gray-400">{new Date(ev.time).toLocaleString('en-IN')}</p>
                    <p className="text-[10px] text-gray-400">by {ev.actor}</p>
                  </li>
                ))}
              </ol>
            )}
          </div>

          {/* Assignment */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <User className="h-4 w-4 text-green-600" /> Assignment
            </h3>
            <div className="space-y-2 text-xs text-gray-600">
              <div className="flex justify-between">
                <span className="text-gray-400">Department</span>
                <span className="font-medium">{caseData.department_id ?? 'Unassigned'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Ward</span>
                <span className="font-medium">{caseData.ward_id ?? '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Priority</span>
                <span className="font-medium">{caseData.priority}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Category</span>
                <span className="font-medium">{caseData.category ?? '—'}</span>
              </div>
            </div>
          </div>

          {/* Resolution evidence placeholder */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" /> Resolution Evidence
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {[1, 2].map((i) => (
                <div key={i} className="bg-gray-50 rounded-lg aspect-video flex flex-col items-center justify-center text-gray-300 border border-dashed border-gray-200">
                  <Camera className="h-5 w-5" />
                  <span className="text-[10px] mt-1">Field photo {i}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-gray-400 mt-2 italic">Uploaded by field worker after work order completion.</p>
          </div>

          {/* Citizen verification */}
          <div className="civic-card p-5 rounded-xl border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" /> Citizen Verification
            </h3>
            <p className="text-xs text-gray-400">
              Verification pending. Citizen will be notified when resolution evidence is submitted.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CaseDetailPage;
