/**
 * A13 — Settings
 * Accordions: SLA classes, priority score and thresholds, AI thresholds,
 * categories and departments, languages.
 *
 * Gap: no settings endpoints. Renders values from a static copy of the
 * config files (taxonomy.v1.json, triage_rules.v1.json, fusion_policy.v1.json,
 * ai_policy.v1.json) and shows the needsBackend banner.
 * Saving needs an audited endpoint.
 */
import React, { useState } from 'react';
import { Shield, ChevronDown, ChevronRight } from 'lucide-react';

interface AccordionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

function Accordion({ title, defaultOpen = false, children }: AccordionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="cc-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-5 py-4 flex items-center justify-between border-b-2 border-ink text-left hover:bg-lime-tint transition-colors"
      >
        <h3 className="font-display text-sm text-ink">{title}</h3>
        {open ? <ChevronDown className="h-4 w-4 text-muted" /> : <ChevronRight className="h-4 w-4 text-muted" />}
      </button>
      {open && <div className="p-5">{children}</div>}
    </div>
  );
}

const slaClasses = [
  { label: 'Critical', hours: 4, description: 'Life-threatening or city-wide impact' },
  { label: 'High', hours: 12, description: 'Safety risk or significant disruption' },
  { label: 'Normal', hours: 48, description: 'Standard municipal complaint' },
  { label: 'Low', hours: 168, description: 'Minor inconvenience or cosmetic' },
];

const priorityThresholds = [
  { range: '90-100', label: 'URGENT', color: 'fire' },
  { range: '70-89', label: 'HIGH', color: 'amber' },
  { range: '40-69', label: 'NORMAL', color: 'ink' },
  { range: '0-39', label: 'LOW', color: 'muted' },
];

const aiThresholds = [
  { setting: 'Auto-assign confidence threshold', value: '0.85' },
  { setting: 'Duplicate detection threshold', value: '0.80' },
  { setting: 'Geospatial cluster radius (m)', value: '800' },
  { setting: 'Temporal window (days)', value: '7' },
  { setting: 'Minimum evidence for AI triage', value: '1 image OR 1 audio' },
];

const categories = [
  'Road Damage', 'Street Lighting', 'Sanitation', 'Water Supply',
  'Drainage', 'Garbage', 'Public Property', 'Noise', 'Encroachment', 'Other',
];

const departments = [
  'Road Maintenance', 'Electrical', 'Sanitation', 'Water Works',
  'Garbage Management', 'Public Works', 'Drainage',
];

const languages = [
  { code: 'en', name: 'English', status: 'Active' },
  { code: 'hi', name: 'Hindi', status: 'Active' },
  { code: 'bn', name: 'Bengali', status: 'Planned' },
  { code: 'ho', name: 'Ho (Mundari)', status: 'Planned' },
];

const SystemSettingsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A13</div>
        <h1 className="cc-title cc-headline-pop">Settings</h1>
      </div>

      {/* Needs Backend banner */}
      <div className="cc-banner-needs-backend cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <Shield className="h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold text-sm">Needs Backend</p>
          <p className="text-xs">Settings require GET/PUT /admin/settings endpoints (audited). Values shown are from static config files.</p>
        </div>
      </div>

      {/* Accordions */}
      <div className="space-y-4">
        {/* SLA Classes */}
        <Accordion title="SLA Classes" defaultOpen>
          <div className="space-y-3">
            {slaClasses.map((sla) => (
              <div key={sla.label} className="flex items-center justify-between py-3 border-b border-dot last:border-0">
                <div>
                  <p className="text-sm font-semibold text-ink">{sla.label}</p>
                  <p className="text-xs text-muted">{sla.description}</p>
                </div>
                <div className="cc-chip text-xs">
                  {sla.hours}h
                </div>
              </div>
            ))}
          </div>
        </Accordion>

        {/* Priority Score Thresholds */}
        <Accordion title="Priority Score Thresholds">
          <div className="space-y-3">
            {priorityThresholds.map((pt) => (
              <div key={pt.label} className="flex items-center justify-between py-3 border-b border-dot last:border-0">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-muted w-16">{pt.range}</span>
                  <span className={`cc-chip text-[11px] ${
                    pt.label === 'URGENT' ? 'cc-priority-urgent' :
                    pt.label === 'HIGH' ? 'cc-priority-high' :
                    'cc-priority-normal'
                  }`}>
                    {pt.label}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Accordion>

        {/* AI Thresholds */}
        <Accordion title="AI Thresholds">
          <div className="space-y-3">
            {aiThresholds.map((at) => (
              <div key={at.setting} className="flex items-center justify-between py-3 border-b border-dot last:border-0">
                <span className="text-sm text-ink">{at.setting}</span>
                <span className="cc-chip font-mono text-xs">{at.value}</span>
              </div>
            ))}
          </div>
        </Accordion>

        {/* Categories & Departments */}
        <Accordion title="Categories & Departments">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-xs font-mono text-muted uppercase mb-3">Categories</h4>
              <div className="flex flex-wrap gap-2">
                {categories.map(c => (
                  <span key={c} className="cc-chip text-[11px]">{c}</span>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs font-mono text-muted uppercase mb-3">Departments</h4>
              <div className="flex flex-wrap gap-2">
                {departments.map(d => (
                  <span key={d} className="cc-chip text-[11px]">{d}</span>
                ))}
              </div>
            </div>
          </div>
        </Accordion>

        {/* Languages */}
        <Accordion title="Languages">
          <div className="space-y-3">
            {languages.map((lang) => (
              <div key={lang.code} className="flex items-center justify-between py-3 border-b border-dot last:border-0">
                <div className="flex items-center gap-3">
                  <span className="cc-chip text-[10px] font-mono">{lang.code}</span>
                  <span className="text-sm text-ink">{lang.name}</span>
                </div>
                <span className={`cc-chip text-[10px] ${lang.status === 'Active' ? 'bg-lime text-ink' : 'bg-dot text-muted'}`}>
                  {lang.status}
                </span>
              </div>
            ))}
          </div>
        </Accordion>
      </div>
    </div>
  );
};

export default SystemSettingsPage;
