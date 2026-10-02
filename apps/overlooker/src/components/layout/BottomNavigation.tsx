import React from 'react';
import { Home, FileText, BarChart3, Users, User, Activity } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
}

const navItems: NavItem[] = [
  { id: 'home',           label: 'Home',      icon: Home,     path: '/' },
  { id: 'issues',         label: 'Issues',    icon: FileText, path: '/issues' },
  { id: 'city-situation', label: 'City',      icon: Activity, path: '/city-situation' },
  { id: 'community',      label: 'Community', icon: Users,    path: '/community' },
  { id: 'profile',        label: 'Profile',   icon: User,     path: '/profile' },
];

const BottomNavigation: React.FC = () => {
  const location = useLocation();

  return (
    <nav className="floating-nav">
      <div className="flex items-center justify-around py-2 px-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <Link
              key={item.id}
              to={item.path}
              className={cn(
                "relative flex flex-col items-center gap-0.5 py-2 px-3 rounded-xl transition-all duration-300",
                isActive 
                  ? "text-emerald-700" 
                  : "text-gray-400 hover:text-gray-600"
              )}
            >
              {/* Active indicator */}
              {isActive && (
                <div
                  className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-6 h-1 rounded-full"
                  style={{ background: 'linear-gradient(90deg, #16a34a, #22c55e)' }}
                />
              )}
              <div className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300",
                isActive 
                  ? "bg-emerald-50 text-emerald-600" 
                  : "text-gray-400"
              )}>
                <Icon className="w-5 h-5" />
              </div>
              <span className={cn(
                "text-[10px] font-semibold transition-colors duration-300",
                isActive ? "text-emerald-700" : "text-gray-400"
              )}>
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
};

export default BottomNavigation;