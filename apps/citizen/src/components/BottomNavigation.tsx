import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Home, FileText, Camera, Users, User } from 'lucide-react';
import { motion } from 'framer-motion';

const BottomNavigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const tabs = [
    { id: 'home', label: 'Home', icon: Home, path: '/dashboard' },
    { id: 'reports', label: 'Reports', icon: FileText, path: '/my-reports' },
    { id: 'report', label: 'Report', icon: Camera, path: '/report', isMain: true },
    { id: 'community', label: 'Community', icon: Users, path: '/community' },
    { id: 'profile', label: 'Profile', icon: User, path: '/profile' },
  ];

  return (
    <div className="nav-bottom safe-area-bottom">
      <div className="flex justify-around items-center px-2 py-2 relative">
        {tabs.map((tab) => {
          const isActive = location.pathname === tab.path;
          const IconComponent = tab.icon;

          if (tab.isMain) {
            return (
              <motion.button
                key={tab.id}
                onClick={() => navigate(tab.path)}
                whileTap={{ scale: 0.9 }}
                className="nav-main-btn"
              >
                <IconComponent className="w-6 h-6" />
                {/* Pulse ring */}
                <span className="absolute inset-0 rounded-2xl animate-pulse-glow" />
              </motion.button>
            );
          }

          return (
            <motion.button
              key={tab.id}
              onClick={() => navigate(tab.path)}
              whileTap={{ scale: 0.9 }}
              className={`nav-item relative ${isActive ? 'active' : ''}`}
            >
              {/* Active indicator */}
              {isActive && (
                <motion.div
                  layoutId="nav-indicator"
                  className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-6 h-1 rounded-full"
                  style={{ background: 'linear-gradient(90deg, #1a7a2e, #27a94a)' }}
                  transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                />
              )}
              <IconComponent className={`nav-icon w-5 h-5 transition-all duration-300 ${isActive ? 'text-emerald-600' : 'text-gray-400'}`} />
              <span className={`text-[10px] font-semibold transition-colors duration-300 ${isActive ? 'text-emerald-700' : 'text-gray-400'}`}>
                {tab.label}
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
};

export default BottomNavigation;
