/**
 * AdminLayout — persistent shell for all authenticated admin pages.
 * Renders Sidebar + Header, then the child route via <Outlet />.
 */
import React, { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { clearTokens } from '../lib/api';

const AdminLayout: React.FC = () => {
  const navigate = useNavigate();
  // Placeholder until useMe() hook is wired
  const [userRole] = useState<'admin' | 'overseer'>('admin');
  const [userDepartment] = useState('City Administration');

  const handleLogout = () => {
    clearTokens();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(180deg, hsl(140,30%,97%) 0%, hsl(140,25%,95%) 100%)' }}>
      <Sidebar />
      <Header
        userRole={userRole}
        userDepartment={userDepartment}
        onLogout={handleLogout}
      />
      {/* Main content area — offset for sidebar (w-64) and header */}
      <main className="ml-64 pt-[72px] min-h-screen">
        <div className="page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default AdminLayout;
