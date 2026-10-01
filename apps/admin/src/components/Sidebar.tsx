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
} from 'lucide-react';

const navItems = [
  { to: '/dashboard',              label: 'Dashboard',             icon: Home },
  { to: '/cases',                  label: 'Case Management',        icon: FolderOpen },
  { to: '/map',                    label: 'City Map',               icon: Map },
  { to: '/ward-heatmap',           label: 'Ward Heatmap',           icon: Layers },
  { to: '/departments',            label: 'Dept. Coordination',     icon: Building2 },
  { to: '/departments/performance',label: 'Dept. Performance',      icon: TrendingUp },
  { to: '/analytics',              label: 'Analytics',              icon: BarChart3 },
  { to: '/incidents',              label: 'Incident Boards',        icon: AlertTriangle },
  { to: '/users',                  label: 'User Management',        icon: Users },
  { to: '/settings',               label: 'System Settings',        icon: Settings },
];

const Sidebar: React.FC = () => {
  return (
    <div className="fixed left-0 top-0 w-64 h-full bg-white border-r border-gray-200 z-20 flex flex-col">
      {/* Logo */}
      <div className="p-5 border-b border-gray-200">
        <h1 className="text-2xl font-bold text-green-600">CivicConnect</h1>
        <p className="text-xs text-gray-400 mt-0.5">Admin Portal · Jharkhand</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/cases' /* exact match so /cases/:id doesn't highlight */}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-green-50 text-green-700 border-r-2 border-green-600'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`
            }
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* AI Triage shortcut */}
      <div className="p-4 border-t border-gray-100">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <BrainCircuit className="h-3.5 w-3.5" />
          <span>AI Triage: open from case detail</span>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;