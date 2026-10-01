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
    {
      id: '1',
      title: 'Issue Status Updated',
      description: 'Your report "Large Pothole on Main Street" is now in progress',
      date: '2024-01-15',
      type: 'status',
      read: false,
      icon: '🔄'
    },
    {
      id: '2',
      title: 'Issue Getting Attention',
      description: 'Your report has received 5+ upvotes from the community',
      date: '2024-01-14',
      type: 'upvote',
      read: false,
      icon: '❤️'
    },
    {
      id: '3',
      title: 'Issue Resolved',
      description: 'Great news! "Street Light Not Working" has been resolved',
      date: '2024-01-13',
      type: 'resolved',
      read: true,
      icon: '✅'
    },
    {
      id: '4',
      title: 'New Issue in Your Area',
      description: 'Water pipe leakage reported near your location',
      date: '2024-01-12',
      type: 'area',
      read: true,
      icon: '📍'
    }
  ];

  const notifications = [...state.notifications, ...mockNotifications];

  const markAsRead = (id: string) => {
    // In a real app, this would update the notification status
    console.log('Mark as read:', id);
  };

  const clearAll = () => {
    if (window.confirm('Are you sure you want to clear all notifications?')) {
      // Clear notifications
      console.log('Clear all notifications');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 hover:bg-gray-100 rounded-full transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <h1 className="text-lg font-semibold text-gray-800">Notifications</h1>
          </div>
          
          {notifications.length > 0 && (
            <button
              onClick={clearAll}
              className="text-sm text-red-600 hover:text-red-700 flex items-center space-x-1"
            >
              <Trash2 className="w-4 h-4" />
              <span>Clear All</span>
            </button>
          )}
        </div>
      </div>

      {/* Notifications List */}
      <div className="p-4 space-y-3">
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Bell className="w-16 h-16 text-gray-400 mb-4" />
            <p className="text-gray-600 text-center">No notifications yet</p>
            <p className="text-sm text-gray-500 text-center mt-2">
              You'll receive updates about your reports and community activity here
            </p>
          </div>
        ) : (
          notifications.map((notification) => (
            <motion.div
              key={notification.id}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className={`bg-white rounded-xl shadow-sm p-4 transition-all duration-200 ${
                !notification.read ? 'border-l-4 border-green-500' : ''
              }`}
            >
              <div className="flex items-start space-x-4">
                {/* Icon */}
                <div className="flex-shrink-0 w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
                  <span className="text-lg">{notification.icon}</span>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between mb-1">
                    <h3 className={`font-medium ${
                      !notification.read ? 'text-gray-900' : 'text-gray-700'
                    }`}>
                      {notification.title}
                    </h3>
                    {!notification.read && (
                      <button
                        onClick={() => markAsRead(notification.id)}
                        className="flex-shrink-0 p-1 hover:bg-gray-100 rounded-full transition-colors ml-2"
                      >
                        <Check className="w-4 h-4 text-green-600" />
                      </button>
                    )}
                  </div>
                  
                  <p className={`text-sm mb-2 ${
                    !notification.read ? 'text-gray-700' : 'text-gray-600'
                  }`}>
                    {notification.description}
                  </p>
                  
                  <p className="text-xs text-gray-500">
                    {new Date(notification.date).toLocaleDateString()} • {notification.type}
                  </p>
                </div>

                {/* Unread indicator */}
                {!notification.read && (
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2"></div>
                )}
              </div>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
};

export default Notifications;