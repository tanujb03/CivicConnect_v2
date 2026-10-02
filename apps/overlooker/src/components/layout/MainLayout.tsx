import React from 'react';
import BottomNavigation from './BottomNavigation';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(180deg, hsl(140,25%,99%) 0%, hsl(140,20%,96%) 100%)' }}>
      <main className="pb-20 page-enter">
        {children}
      </main>
      <BottomNavigation />
    </div>
  );
};

export default MainLayout;