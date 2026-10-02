import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Home,
  BarChart3,
  FolderOpen,
  Users,
  Building2,
  AlertTriangle,
  Settings,
  Map,
  Layers,
  TrendingUp,
  BrainCircuit,
  Sparkles,
} from 'lucide-react';

const navItems = [
  { to: '/dashboard',               label: 'Dashboard',          icon: Home },
  { to: '/cases',                   label: 'Case Management',    icon: FolderOpen },
  { to: '/map',                     label: 'City Map',           icon: Map },
  { to: '/ward-heatmap',            label: 'Ward Heatmap',       icon: Layers },
  { to: '/departments',             label: 'Dept. Coordination', icon: Building2 },
  { to: '/departments/performance', label: 'Dept. Performance',  icon: TrendingUp },
  { to: '/analytics',               label: 'Analytics',          icon: BarChart3 },
  { to: '/incidents',               label: 'Incident Boards',    icon: AlertTriangle },
  { to: '/users',                   label: 'User Management',    icon: Users },
  { to: '/settings',                label: 'System Settings',    icon: Settings },
];

const Sidebar: React.FC = () => {
  return (
    <div className="fixed left-0 top-0 w-64 h-full sidebar-premium z-20 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-emerald-100/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center relative"
               style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)' }}>
            <Sparkles className="w-5 h-5 text-white" />
            <div className="absolute inset-0 rounded-xl" style={{ boxShadow: '0 4px 15px rgba(22, 163, 74, 0.25)' }} />
          </div>
          <div>
            <h1 className="text-lg font-extrabold tracking-tight" style={{ 
              background: 'linear-gradient(135deg, #0d4a1a, #1a7a2e)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>CivicConnect</h1>
            <p className="text-[10px] text-gray-400 font-medium tracking-wider uppercase">Admin Portal • Jharkhand</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/cases'}
            className={({ isActive }) =>
              `group flex items-center gap-3 px-4 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-300 ${
                isActive
                  ? 'bg-emerald-50/80 text-emerald-700 shadow-sm border border-emerald-100/50'
                  : 'text-gray-500 hover:bg-emerald-50/40 hover:text-gray-700'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300 ${
                  isActive 
                    ? 'bg-emerald-100/80 text-emerald-600' 
                    : 'bg-gray-100/50 text-gray-400 group-hover:bg-emerald-50 group-hover:text-emerald-500'
                }`}>
                  <Icon className="h-4 w-4" />
                </div>
                <span>{label}</span>
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-500" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* AI Triage shortcut */}
      <div className="p-4 mx-3 mb-3 rounded-xl bg-gradient-to-br from-emerald-50 to-emerald-100/50 border border-emerald-200/30">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
               style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)' }}>
            <BrainCircuit className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-xs font-semibold text-emerald-800">AI Triage</p>
            <p className="text-[10px] text-emerald-600/70">Open from case detail</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;