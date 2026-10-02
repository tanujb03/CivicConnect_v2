import React from 'react';
import { motion } from 'framer-motion';
import { 
  Edit, 
  Key, 
  Moon, 
  Sun, 
  Globe, 
  Bell, 
  Shield, 
  HelpCircle, 
  LogOut,
  ChevronRight,
  MapPin
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { useNavigate } from 'react-router-dom';
import BottomNavigation from './BottomNavigation';

const Profile: React.FC = () => {
  const { state, dispatch } = useApp();
  const navigate = useNavigate();

  const handleLogout = () => {
    if (window.confirm('Are you sure you want to logout?')) {
      dispatch({ type: 'SET_USER', payload: null as any });
      navigate('/');
    }
  };

  const toggleDarkMode = () => {
    dispatch({ type: 'TOGGLE_DARK_MODE' });
  };

  const menuItems = [
    {
      title: 'Account Settings',
      items: [
        {
          icon: Edit,
          label: 'Edit Profile',
          action: () => {},
          description: 'Update your personal information'
        },
        {
          icon: Key,
          label: 'Change Password',
          action: () => {},
          description: 'Update your password'
        }
      ]
    },
    {
      title: 'App Preferences',
      items: [
        {
          icon: state.darkMode ? Sun : Moon,
          label: 'Dark Mode',
          action: toggleDarkMode,
          description: state.darkMode ? 'Switch to light mode' : 'Switch to dark mode',
          rightElement: (
            <div className={`w-12 h-6 rounded-full p-1 transition-all duration-300 ${
              state.darkMode ? 'bg-emerald-600' : 'bg-gray-300'
            }`}>
              <div className={`w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-300 ${
                state.darkMode ? 'translate-x-6' : 'translate-x-0'
              }`} />
            </div>
          )
        },
        {
          icon: Globe,
          label: 'Language',
          action: () => {},
          description: 'Change app language',
          rightElement: (
            <span className="text-sm text-gray-400 font-medium">
              {state.language === 'en' ? 'English' : 'हिन्दी'}
            </span>
          )
        }
      ]
    },
    {
      title: 'Notifications',
      items: [
        {
          icon: Bell,
          label: 'Push Notifications',
          action: () => {},
          description: 'Get notified about issue updates',
          rightElement: (
            <div className="w-12 h-6 rounded-full p-1 bg-emerald-600">
              <div className="w-4 h-4 rounded-full bg-white shadow-sm translate-x-6" />
            </div>
          )
        }
      ]
    },
    {
      title: 'Help & Support',
      items: [
        {
          icon: Shield,
          label: 'Privacy Policy',
          action: () => {},
          description: 'Read our privacy policy'
        },
        {
          icon: HelpCircle,
          label: 'Help & Support',
          action: () => {},
          description: 'Get help and contact support'
        }
      ]
    }
  ];

  return (
    <div className="min-h-screen pb-24 bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec]">
      {/* Premium Header */}
      <div className="header-civic text-white px-6 pt-8 pb-10 relative">
        <div className="flex items-center gap-4">
          <div className="w-18 h-18 rounded-2xl overflow-hidden border-2 border-white/20 shadow-xl bg-white/10 p-0.5">
            <img
              src={state.user?.avatar || 'https://images.pexels.com/photos/771742/pexels-photo-771742.jpeg?auto=compress&cs=tinysrgb&w=100&h=100&fit=crop'}
              alt="Profile"
              className="w-16 h-16 rounded-xl object-cover"
            />
          </div>
          <div>
            <h2 className="text-xl font-extrabold tracking-tight">{state.user?.name || 'User'}</h2>
            <p className="text-white/60 text-sm font-medium mt-0.5">{state.user?.phone || '+91 XXXXX XXXXX'}</p>
            <div className="flex items-center gap-1.5 mt-1">
              <MapPin className="w-3 h-3 text-white/40" />
              <p className="text-white/40 text-xs font-medium">{state.user?.address || 'Ranchi, Jharkhand'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Menu Items */}
      <div className="px-5 -mt-4 space-y-5">
        {menuItems.map((section, sectionIndex) => (
          <motion.div
            key={sectionIndex}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: sectionIndex * 0.08 }}
            className="space-y-2"
          >
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 px-1">
              {section.title}
            </h3>
            <div className="glass-card overflow-hidden">
              {section.items.map((item, itemIndex) => {
                const IconComponent = item.icon;
                return (
                  <button
                    key={itemIndex}
                    onClick={item.action}
                    className="w-full flex items-center justify-between p-4 transition-all duration-300 border-b last:border-b-0 border-gray-100/50 hover:bg-emerald-50/30 group"
                  >
                    <div className="flex items-center gap-3.5">
                      <div className="w-9 h-9 rounded-xl bg-gray-50 flex items-center justify-center group-hover:bg-emerald-50 transition-colors">
                        <IconComponent className="w-4.5 h-4.5 text-gray-500 group-hover:text-emerald-600 transition-colors" />
                      </div>
                      <div className="text-left">
                        <p className="font-semibold text-gray-800 text-[14px]">{item.label}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{item.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center">
                      {item.rightElement || <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />}
                    </div>
                  </button>
                );
              })}
            </div>
          </motion.div>
        ))}

        {/* Logout Button */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="pt-2"
        >
          <button
            onClick={handleLogout}
            className="w-full font-semibold py-4 rounded-2xl transition-all duration-300 flex items-center justify-center gap-2 bg-red-50 hover:bg-red-100 text-red-600 border border-red-100/50"
          >
            <LogOut className="w-4.5 h-4.5" />
            <span>Logout</span>
          </button>
        </motion.div>
      </div>

      <BottomNavigation />
    </div>
  );
};

export default Profile;