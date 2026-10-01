import React, { useState, useEffect } from 'react';
import LoginPage from '@/components/LoginPage';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import Dashboard from '@/components/Dashboard';
import AnalyticsPage from '@/components/AnalyticsPage';
import IssueManagementPage from '@/components/IssueManagementPage';
import UserManagementPage from '@/components/UserManagementPage';
import DepartmentCoordinationPage from '@/components/DepartmentCoordinationPage';
import SpecialBoardsPage from '@/components/SpecialBoardsPage';
import SystemSettingsPage from '@/components/SystemSettingsPage';

const Index = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userRole, setUserRole] = useState<'admin' | 'overseer'>('admin');
  const [userDepartment, setUserDepartment] = useState('');
  const [activeItem, setActiveItem] = useState('dashboard');

  // Auto-refresh dashboard stats every 30 seconds
  useEffect(() => {
    if (isLoggedIn && activeItem === 'dashboard') {
      const interval = setInterval(() => {
        console.log('Auto-refreshing dashboard stats...');
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [isLoggedIn, activeItem]);

  const handleLogin = (role: 'admin' | 'overseer', department: string) => {
    setUserRole(role);
    setUserDepartment(department);
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    setActiveItem('dashboard');
  };

  const renderContent = () => {
    switch (activeItem) {
      case 'dashboard':
        return <Dashboard />;
      case 'analytics':
        return <AnalyticsPage />;
      case 'issues':
        return <IssueManagementPage />;
      case 'users':
        return <UserManagementPage />;
      case 'departments':
        return <DepartmentCoordinationPage />;
      case 'special':
        return <SpecialBoardsPage userRole={userRole} />;
      case 'settings':
        return <SystemSettingsPage />;
      default:
        return <Dashboard />;
    }
  };

  if (!isLoggedIn) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-civic-bg">
      <Sidebar activeItem={activeItem} onItemClick={setActiveItem} />
      <Header 
        userRole={userRole} 
        userDepartment={userDepartment} 
        onLogout={handleLogout} 
      />
      {renderContent()}
    </div>
  );
};

export default Index;
