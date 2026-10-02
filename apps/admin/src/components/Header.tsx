import React, { useState, useEffect } from 'react';
import { Bell, User, LogOut, ChevronDown } from 'lucide-react';
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
    <header className="fixed top-0 left-64 right-0 z-10 bg-gradient-to-r from-[#1A531A] to-[#3d7a1a] border-b border-green-800/30 px-6 h-[72px] flex items-center">
      <div className="flex justify-between items-center w-full">
        {/* Title */}
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">Admin Portal</h1>
          <span className="text-green-300/60">|</span>
          <span className="text-green-200 text-sm">Ranchi Municipal Corporation</span>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-5">
          {/* Live clock */}
          <span className="text-xs text-green-200 hidden lg:block">
            {currentTime.toLocaleDateString('en-IN', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>

          {/* Notifications — count is mock until real notification hook */}
          <div className="relative">
            <Button variant="ghost" size="icon" className="text-white hover:bg-white/10">
              <Bell className="h-5 w-5" />
              <Badge className="absolute -top-1 -right-1 h-4 w-4 p-0 flex items-center justify-center bg-red-500 text-white text-[10px]">
                3
              </Badge>
            </Button>
          </div>

          {/* User dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="flex items-center gap-2 text-white hover:bg-white/10">
                <div className="h-7 w-7 rounded-full bg-white/20 flex items-center justify-center">
                  <User className="h-4 w-4" />
                </div>
                <div className="text-left hidden sm:block">
                  <div className="text-xs font-semibold capitalize">{userRole}</div>
                  <div className="text-[10px] text-green-200 truncate max-w-[120px]">{userDepartment}</div>
                </div>
                <ChevronDown className="h-3.5 w-3.5 opacity-70" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem className="cursor-default">
                <User className="mr-2 h-4 w-4" />
                <span>Profile Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onLogout} className="text-red-600 focus:text-red-600">
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