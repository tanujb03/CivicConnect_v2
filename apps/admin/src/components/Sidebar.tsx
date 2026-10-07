import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Home,
  FolderOpen,
  Map,
  Layers,
  Building2,
  TrendingUp,
  BarChart3,
  AlertTriangle,
  Users,
  Settings,
  BrainCircuit,
} from 'lucide-react';

// Eleven nav links as the plan specifies
const navItems = [
  { to: '/dashboard',               label: 'Operations',          icon: Home },
  { to: '/cases',                   label: 'Case Workbench',      icon: FolderOpen,     badgeKey: 'unassigned' },
  { to: '/map',                     label: 'City Map',            icon: Map },
  { to: '/ward-heatmap',            label: 'Ward Heatmap',        icon: Layers },
  { to: '/departments',             label: 'Departments',         icon: Building2 },
  { to: '/departments/performance', label: 'Performance',         icon: TrendingUp },
  { to: '/analytics',               label: 'Analytics',           icon: BarChart3 },
  { to: '/incidents',               label: 'Incidents',           icon: AlertTriangle,  badgeKey: 'incidents' },
  { to: '/users',                   label: 'Users',               icon: Users },
  { to: '/settings',                label: 'Settings',            icon: Settings },
  { to: '/ai-triage',               label: 'AI Triage',           icon: BrainCircuit },
];

const Sidebar: React.FC = () => {
  return (
    <div className="admin-sidebar">
      {/* Logo with slow-spinning rosette */}
      <div className="p-6 border-b-2 border-ink">
        <div className="flex items-center gap-3">
          <div className="relative">
            {/* Rosette ring that spins slowly behind the logo mark */}
            <div
              className="w-10 h-10 rounded-lg border-2 border-ink flex items-center justify-center"
              style={{ background: 'var(--wine)' }}
            >
              <span className="text-on-wine font-display text-sm">CC</span>
            </div>
            <div
              className="absolute inset-[-4px] rounded-xl border-2 border-dashed border-wine/40 cc-rosette pointer-events-none"
              aria-hidden="true"
            />
          </div>
          <div>
            <h1 className="text-lg font-display tracking-tight text-ink">
              CivicConnect
            </h1>
            <p className="text-[10px] font-mono text-muted uppercase tracking-wider">
              Admin Portal
            </p>
          </div>
        </div>
      </div>

      {/* Navigation links */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1" aria-label="Main navigation">
        {navItems.map(({ to, label, icon: Icon, badgeKey }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/cases' || to === '/dashboard'}
            className={({ isActive }) =>
              `admin-nav-link group flex items-center gap-3 px-3 py-2.5 text-[13px] font-medium ${
                isActive
                  ? 'admin-nav-active'
                  : 'text-muted hover:text-ink'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span className="flex-1">{label}</span>
                {/* Badge placeholder for unassigned count or incident count */}
                {badgeKey && (
                  <span
                    className={`cc-chip text-[10px] py-0.5 px-2 ${
                      isActive ? 'border-ink bg-surface text-ink' : 'border-muted/30 text-muted'
                    }`}
                  >
                    {badgeKey === 'unassigned' ? '17' : '2'}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* SYNTHETIC DEMO DATA sticker at the bottom */}
      <div className="p-4 flex justify-center">
        <div className="cc-sticker">
          Synthetic Demo Data
        </div>
      </div>
    </div>
  );
};

export default Sidebar;