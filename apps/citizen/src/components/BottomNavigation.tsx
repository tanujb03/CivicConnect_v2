import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Home, FileText, Camera, Users, User } from 'lucide-react';

const BottomNavigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const tabs = [
    { id: 'home', label: 'Home', icon: Home, path: '/dashboard' },
    { id: 'reports', label: 'My Reports', icon: FileText, path: '/my-reports' },
    { id: 'report', label: 'Report', icon: Camera, path: '/report', isMain: true },
    { id: 'community', label: 'Community', icon: Users, path: '/community' },
    { id: 'profile', label: 'Profile', icon: User, path: '/profile' }
  ];

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-2 z-50">
      <div className="flex justify-around items-center relative">
        {tabs.map((tab) => {
          const isActive = location.pathname === tab.path;
          const IconComponent = tab.icon;

         // ... (imports and component setup)

          if (tab.isMain) {
            return (
              <button
                key={tab.id}
                onClick={() => navigate(tab.path)}
                // CHANGE: Applied the new gradient and sizing
                className="w-16 h-16 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white rounded-full shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105 -mt-8 z-50 flex items-center justify-center"
              >
                <IconComponent className="w-7 h-7" />
              </button>
            );
          }

       return (
  <button
    key={tab.id}
    onClick={() => navigate(tab.path)}
    // CHANGE 1: Added `relative` for positioning and adjusted padding
    className={`relative flex flex-col items-center space-y-1 pt-3 pb-2 px-3 rounded-lg transition-colors ${
      isActive ? 'text-[#1A531A]' : 'text-[#6B7280] hover:text-[#1A531A]'
    }`}
  >
    {/* CHANGE 2: Added this new div for the indicator line */}
    {isActive && (
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-1 bg-gray-800 rounded-full"></div>
    )}
    
    <IconComponent className="w-5 h-5" />
    <span className="text-xs font-medium">{tab.label}</span>
  </button>
);
          
// ... (rest of the component)
        })}
      </div>
    </div>
  );
};

export default BottomNavigation;
