import React from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Check, Bell, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

const Notifications: React.FC = () => {
  const navigate = useNavigate();
  const { state, dispatch } = useApp();

  // Mock notifications since we don't have a full notification system
  const mockNotifications = [
    { id: '1', title: 'Issue Status Updated', description: 'Your report "Large Pothole on Main Street" is now in progress', date: '2024-01-15', type: 'status', read: false, icon: '🔄' },
    { id: '2', title: 'Issue Getting Attention', description: 'Your report has received 5+ upvotes from the community', date: '2024-01-14', type: 'upvote', read: false, icon: '❤️' },
    { id: '3', title: 'Issue Resolved', description: 'Great news! "Street Light Not Working" has been resolved', date: '2024-01-13', type: 'resolved', read: true, icon: '✅' },
    { id: '4', title: 'New Issue in Your Area', description: 'Water pipe leakage reported near your location', date: '2024-01-12', type: 'area', read: true, icon: '📍' },
  ];

  const notifications = [...state.notifications, ...mockNotifications];

  const markAsRead = (id: string) => {
    console.log('Mark as read:', id);
  };

  const clearAll = () => {
    if (window.confirm('Are you sure you want to clear all notifications?')) {
      console.log('Clear all notifications');
    }
  };

  const getTypeBorder = (type: string) => {
    switch (type) {
      case 'status': return 'border-l-blue-400';
      case 'upvote': return 'border-l-rose-400';
      case 'resolved': return 'border-l-emerald-400';
      case 'area': return 'border-l-amber-400';
      default: return 'border-l-gray-300';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec]">
      {/* Premium Header */}
      <div className="bg-white/80 backdrop-blur-xl border-b border-emerald-100/50 px-5 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="w-10 h-10 rounded-xl bg-gray-50 hover:bg-gray-100 flex items-center justify-center transition-all duration-300"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-lg font-bold text-gray-900">Notifications</h1>
              <p className="text-[11px] text-gray-400 font-medium">{notifications.filter(n => !n.read).length} unread</p>
            </div>
          </div>
          
          {notifications.length > 0 && (
            <button
              onClick={clearAll}
              className="text-xs text-red-500 hover:text-red-600 flex items-center gap-1.5 font-semibold px-3 py-1.5 rounded-lg hover:bg-red-50 transition-all"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear All</span>
            </button>
          )}
        </div>
      </div>

      {/* Notifications List */}
      <div className="px-5 pt-4 pb-8 space-y-2.5">
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
              <Bell className="w-7 h-7 text-gray-400" />
            </div>
            <p className="text-gray-500 font-semibold">No notifications yet</p>
            <p className="text-sm text-gray-400 text-center mt-1.5 max-w-xs">
              You'll receive updates about your reports and community activity here
            </p>
          </div>
        ) : (
          notifications.map((notification, i) => (
            <motion.div
              key={notification.id}
              initial={{ y: 15, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: i * 0.04 }}
              className={`glass-card p-4 transition-all duration-300 border-l-4 ${getTypeBorder(notification.type)} ${
                !notification.read ? 'bg-white shadow-sm' : 'bg-white/60'
              } hover:shadow-glass`}
            >
              <div className="flex items-start gap-3.5">
                {/* Icon */}
                <div className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${
                  !notification.read ? 'bg-emerald-50' : 'bg-gray-50'
                }`}>
                  <span className="text-lg">{notification.icon}</span>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h3 className={`text-[14px] font-semibold ${
                      !notification.read ? 'text-gray-900' : 'text-gray-600'
                    }`}>
                      {notification.title}
                    </h3>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {!notification.read && (
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      )}
                      {!notification.read && (
                        <button
                          onClick={() => markAsRead(notification.id)}
                          className="p-1 hover:bg-emerald-50 rounded-lg transition-colors"
                        >
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        </button>
                      )}
                    </div>
                  </div>
                  
                  <p className={`text-sm leading-relaxed ${
                    !notification.read ? 'text-gray-600' : 'text-gray-400'
                  }`}>
                    {notification.description}
                  </p>
                  
                  <p className="text-[11px] text-gray-400 mt-2 font-medium">
                    {new Date(notification.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </p>
                </div>
              </div>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
};

export default Notifications;