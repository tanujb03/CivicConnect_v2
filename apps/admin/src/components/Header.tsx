import React, { useState, useEffect } from 'react';
import { Bell, User, LogOut, ChevronDown, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';

interface HeaderProps {
  userRole: 'admin' | 'overseer';
  userDepartment: string;
  onLogout: () => void;
}

const Header: React.FC<HeaderProps> = ({ userRole, userDepartment, onLogout }) => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="fixed top-0 left-64 right-0 z-10 header-admin px-6 h-[72px] flex items-center">
      <div className="flex justify-between items-center w-full">
        {/* Title section */}
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Admin Portal</h1>
            <p className="text-[11px] text-emerald-300/50 font-medium">Ranchi Municipal Corporation</p>
          </div>
        </div>

        {/* Search bar */}
        <div className="hidden lg:flex items-center flex-1 max-w-md mx-8">
          <div className="relative w-full">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              type="text"
              placeholder="Search cases, wards, departments..."
              className="w-full pl-10 pr-4 py-2 bg-white/8 border border-white/10 rounded-xl text-sm text-white placeholder-white/25 focus:outline-none focus:bg-white/12 focus:border-white/20 transition-all duration-300 backdrop-blur-sm"
            />
          </div>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-4">
          {/* Live clock */}
          <div className="hidden lg:flex items-center gap-2 bg-white/8 backdrop-blur-sm rounded-xl px-3 py-1.5 border border-white/10">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-white/70 font-medium">
              {currentTime.toLocaleDateString('en-IN', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>

          {/* Notifications */}
          <div className="relative">
            <Button variant="ghost" size="icon" className="text-white/80 hover:bg-white/10 rounded-xl hover:text-white transition-all">
              <Bell className="h-5 w-5" />
              <span className="absolute -top-0.5 -right-0.5 w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-bold text-white"
                    style={{ background: 'linear-gradient(145deg, #ef4444, #dc2626)', boxShadow: '0 2px 8px rgba(239,68,68,0.4)' }}>
                3
              </span>
            </Button>
          </div>

          {/* Divider */}
          <div className="w-px h-8 bg-white/10" />

          {/* User dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="flex items-center gap-3 text-white hover:bg-white/10 rounded-xl px-3 transition-all">
                <div className="h-8 w-8 rounded-xl bg-white/15 flex items-center justify-center border border-white/10 backdrop-blur-sm">
                  <User className="h-4 w-4 text-white/80" />
                </div>
                <div className="text-left hidden sm:block">
                  <div className="text-xs font-semibold capitalize text-white/90">{userRole}</div>
                  <div className="text-[10px] text-emerald-300/40 truncate max-w-[120px]">{userDepartment}</div>
                </div>
                <ChevronDown className="h-3.5 w-3.5 text-white/40" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 rounded-xl shadow-lg border-emerald-100/50 mt-1">
              <DropdownMenuItem className="cursor-pointer rounded-lg">
                <User className="mr-2 h-4 w-4 text-gray-400" />
                <span>Profile Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onLogout} className="text-red-600 focus:text-red-600 cursor-pointer rounded-lg">
                <LogOut className="mr-2 h-4 w-4" />
                <span>Logout</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
};

export default Header;