import React, { useState, useRef, useEffect } from 'react';
import { Bell, User, LogOut, Search, FileText, MapPin, Building2 } from 'lucide-react';

interface HeaderProps {
  userRole: 'admin' | 'overseer';
  userDepartment: string;
  onLogout: () => void;
}

const Header: React.FC<HeaderProps> = ({ userRole, userDepartment, onLogout }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showNotifs, setShowNotifs] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowSearch(false);
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotifs(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const mockSearchResults = [
    { type: 'case', id: 'CC-1042', title: 'Major pothole near school', icon: FileText },
    { type: 'ward', id: 'W12', title: 'Ward 12 Heatmap', icon: MapPin },
    { type: 'dept', id: 'roads', title: 'Road Maintenance', icon: Building2 },
    { type: 'case', id: 'CC-1038', title: 'Raw sewage overflow', icon: FileText },
  ].filter(item => 
    searchQuery && (item.id.toLowerCase().includes(searchQuery.toLowerCase()) || 
    item.title.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const mockNotifs = [
    { id: 1, text: 'W12 hotspot alert — 31 cases', time: '5m ago' },
    { id: 2, text: 'SLA breach approaching: CC-1042', time: '12m ago' },
    { id: 3, text: '12 new cases in last hour', time: '1h ago' },
  ];

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
      <div ref={searchRef} className="hidden lg:flex items-center flex-1 max-w-md mx-8 relative z-50">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="text"
            placeholder="Search cases, wards, departments... (Cmd+K)"
            className="w-full pl-10 pr-4 py-2 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted focus:outline-none focus:ring-2 focus:ring-lime"
            style={{ minHeight: '44px' }}
            aria-label="Search cases, wards, departments"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setShowSearch(true);
            }}
            onFocus={() => setShowSearch(true)}
          />
        </div>
        
        {showSearch && searchQuery && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-surface border-2 border-ink rounded-md shadow-card overflow-hidden">
            {mockSearchResults.length > 0 ? (
              <div className="p-2 space-y-1">
                {mockSearchResults.map(res => (
                  <button key={res.id} className="w-full text-left px-3 py-2 hover:bg-lime-tint rounded-md flex items-center gap-3">
                    <res.icon className="w-4 h-4 text-muted" />
                    <div>
                      <div className="text-xs font-semibold text-ink">{res.title}</div>
                      <div className="text-[10px] font-mono text-muted uppercase">{res.type} {res.id && `· ${res.id}`}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="p-4 text-center text-xs text-muted font-mono">No results found for "{searchQuery}"</div>
            )}
          </div>
        )}
      </div>

      {/* Right: notifications, user */}
      <div className="flex items-center gap-3">
        {/* Notifications */}
        <div ref={notifRef} className="relative">
          <button
            className="relative w-10 h-10 flex items-center justify-center border-2 border-ink rounded-md hover:bg-lime-tint transition-colors"
            aria-label="Notifications"
            onClick={() => setShowNotifs(!showNotifs)}
          >
            <Bell className="h-4 w-4 text-ink" />
            <span
              className="absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-bold"
              style={{ background: 'var(--fire)', color: 'var(--on-fire)' }}
            >
              3
            </span>
          </button>
          
          {showNotifs && (
            <div className="absolute top-full right-0 mt-2 w-80 bg-surface border-2 border-ink rounded-md shadow-card z-50">
              <div className="px-4 py-3 border-b border-dot font-display text-sm">Notifications</div>
              <div className="max-h-80 overflow-y-auto">
                {mockNotifs.map(n => (
                  <div key={n.id} className="px-4 py-3 hover:bg-ground border-b border-dot last:border-b-0 cursor-pointer">
                    <p className="text-xs text-ink">{n.text}</p>
                    <p className="text-[10px] font-mono text-muted mt-1">{n.time}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

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