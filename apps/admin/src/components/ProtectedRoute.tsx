/**
 * ProtectedRoute — Guards all admin routes.
 * Checks localStorage for access token. Redirects to /login if missing.
 * On integration: replace with useMe() hook query status.
 */
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

interface Props {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<Props> = ({ children }) => {
  const location = useLocation();
  const token = localStorage.getItem('civic_access_token');

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
