import React, { useState, useEffect } from 'react';
import { Bell, User, LogOut, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';

interface HeaderProps {
  userRole: 'admin' | 'overseer';
  userDepartment: string;
  onLogout: () => void;
}

const Header: React.FC<HeaderProps> = ({ userRole, userDepartment, onLogout }) => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const formatDateTime = (date: Date) => {
    return date.toLocaleDateString('en-IN', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <header className="ml-64 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] border-b border-gray-200 px-6 py-4">
      <div className="flex justify-between items-center">
        {/* Left Section */}
        <div className="flex items-center space-x-4">
          <h1 className="text-5xl font-bold text-white">Admin Portal</h1>
         <span className="text-white">|</span>
  <span className="text-2xl text-white">Ranchi</span>
        </div>

        {/* Right Section */}
        <div className="flex items-center space-x-6">
          {/* Live Time */}
         <div className="text-sm text-white">
            {formatDateTime(currentTime)}
          </div>

          {/* Notifications */}
          <div className="relative">
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              <Badge className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center bg-red-500 text-white text-xs">
                3
              </Badge>
            </Button>
          </div>

          {/* User Profile */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="flex items-center space-x-2">
                <User className="h-5 w-5" />
                <div className="text-left">
                  <div className="text-sm font-medium capitalize">{userRole}</div>
                  <div className="text-xs text-gray-500">{userDepartment}</div>
                </div>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem>
                <User className="mr-2 h-4 w-4" />
                <span>Profile Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onLogout}>
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