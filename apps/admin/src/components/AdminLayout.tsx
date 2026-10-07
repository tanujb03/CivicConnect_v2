/**
 * AdminLayout — persistent shell for all authenticated admin pages.
 * Renders Sidebar + Header, then the child route via Outlet.
 * Uses the design system tokens from packages/ui/tokens.css.
 * Route changes animate with framer-motion AnimatePresence.
 */
import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import Sidebar from './Sidebar';
import Header from './Header';
import { clearTokens } from '../lib/api';

const AdminLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  // Placeholder until useMe() hook is wired to GET /auth/me
  const [userRole] = useState<'admin' | 'overseer'>('admin');
  const [userDepartment] = useState('City Administration');

  const handleLogout = () => {
    clearTokens();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen" style={{ background: 'var(--ground)' }}>
      <Sidebar />
      <div className="admin-main">
        <Header
          userRole={userRole}
          userDepartment={userDepartment}
          onLogout={handleLogout}
        />
        {/* Route change animation: opacity and 24px rise, 0.4s */}
        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="pt-4"
          >
            <Outlet />
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  );
};

export default AdminLayout;
