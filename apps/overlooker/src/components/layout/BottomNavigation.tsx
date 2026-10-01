import React from 'react';
import { Home, FileText, BarChart3, Users, User } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
}

const navItems: NavItem[] = [
  { id: 'home', label: 'Home', icon: Home, path: '/' },
  { id: 'issues', label: 'Issues', icon: FileText, path: '/issues' },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, path: '/analytics' },
  { id: 'community', label: 'Community', icon: Users, path: '/community' },
  { id: 'profile', label: 'Profile', icon: User, path: '/profile' },
];

const BottomNavigation: React.FC = () => {
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white shadow-lg">
      <div className="flex items-center justify-around py-2 px-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <Link
              key={item.id}
              to={item.path}
              className={cn(
                "flex flex-col items-center space-y-1 py-2 px-3 rounded-xl transition-all duration-300",
                isActive 
                  ? "bg-white/20 text-white scale-110" 
                  : "text-white/80 hover:text-white hover:bg-white/10"
              )}
            >
              <Icon className={cn("w-5 h-5", isActive && "drop-shadow-sm")} />
              <span className={cn(
                "text-xs font-medium",
                isActive ? "text-white" : "text-white/80"
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