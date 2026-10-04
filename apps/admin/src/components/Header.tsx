import React from 'react';
import { Bell, User, LogOut, Search } from 'lucide-react';

interface HeaderProps {
  userRole: 'admin' | 'overseer';
  userDepartment: string;
  onLogout: () => void;
}

const Header: React.FC<HeaderProps> = ({ userRole, userDepartment, onLogout }) => {
  return (
    <header
      className="sticky top-0 z-20 flex items-center justify-between px-6 h-16 border-b-2 border-ink"
      style={{ background: 'var(--surface)' }}
    >
      {/* Left: page context */}
      <div className="flex items-center gap-3">
        <div className="cc-chip text-[10px] py-0.5">
          {userRole === 'admin' ? 'ADMIN' : 'OVERSEER'}
        </div>
        <span className="text-sm text-muted font-mono">{userDepartment}</span>
      </div>

      {/* Center: search bar */}
      <div className="hidden lg:flex items-center flex-1 max-w-md mx-8">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="text"
            placeholder="Search cases, wards, departments... (Cmd+K)"
            className="w-full pl-10 pr-4 py-2 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted focus:outline-none focus:ring-2 focus:ring-lime"
            style={{ minHeight: '44px' }}
            aria-label="Search cases, wards, departments"
          />
        </div>
      </div>

      {/* Right: notifications, user */}
      <div className="flex items-center gap-3">
        {/* Notifications */}
        <button
          className="relative w-10 h-10 flex items-center justify-center border-2 border-ink rounded-md hover:bg-lime-tint transition-colors"
          aria-label="Notifications"
        >
          <Bell className="h-4 w-4 text-ink" />
          <span
            className="absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-bold"
            style={{ background: 'var(--fire)', color: 'var(--on-fire)' }}
          >
            3
          </span>
        </button>

        {/* User info */}
        <button
          onClick={onLogout}
          className="flex items-center gap-2 px-3 py-2 border-2 border-ink rounded-md hover:bg-lime-tint transition-colors"
          aria-label="User menu and logout"
        >
          <div className="w-7 h-7 rounded-md bg-wine flex items-center justify-center">
            <User className="h-3.5 w-3.5 text-on-wine" />
          </div>
          <div className="text-left hidden sm:block">
            <div className="text-xs font-semibold capitalize text-ink">{userRole}</div>
            <div className="text-[10px] font-mono text-muted truncate max-w-[100px]">{userDepartment}</div>
          </div>
          <LogOut className="h-3.5 w-3.5 text-muted ml-1" />
        </button>
      </div>
    </header>
  );
};

export default Header;