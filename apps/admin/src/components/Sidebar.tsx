import React from 'react';
import { Home, BarChart3, FolderOpen, Users, Building2, AlertTriangle, Settings } from 'lucide-react';

interface SidebarProps {
  activeItem: string;
  onItemClick: (item: string) => void;
}

const menuItems = [
  { id: 'dashboard', label: 'Dashboard Overview', icon: Home },
  { id: 'analytics', label: 'Analytics & Reports', icon: BarChart3 },
  { id: 'issues', label: 'Issue Management', icon: FolderOpen },
  { id: 'users', label: 'User Management', icon: Users },
  { id: 'departments', label: 'Department Coordination', icon: Building2 },
  { id: 'special', label: 'Special Boards', icon: AlertTriangle },
  { id: 'settings', label: 'System Settings', icon: Settings },
];

const Sidebar: React.FC<SidebarProps> = ({ activeItem, onItemClick }) => {
  return (
   <div className="fixed left-0 top-0 w-64 h-full bg-white border-r border-gray-200 z-10">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-3xl font-bold text-green-600">CivicConnect</h1>
        
      </div>
      {/* Menu Items */}
      <nav className="mt-6">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeItem === item.id;
          
          return (
            <button
              key={item.id}
              onClick={() => onItemClick(item.id)}
              className={`w-full flex items-center px-4 py-3 text-left transition-colors ${
                isActive 
                  ? 'nav-active' 
                  : 'nav-hover text-gray-700'
              }`}
            >
              <Icon className="mr-3 h-5 w-5" />
              <span className="font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
};

export default Sidebar;