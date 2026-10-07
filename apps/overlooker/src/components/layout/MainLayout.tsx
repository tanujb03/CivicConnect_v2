/**
 * Overlooker Shell — O-Shell
 * No sidebar. Top bar with logo, OVERLOOKER chip, pill nav, Read-only chip.
 * Pill nav tabs: Home, City View, Issues, Analytics, Community, Profile.
 *
 * The overlooker gets a read-only badge and the pill navigation replaces
 * the admin sidebar. No bottom navigation on desktop.
 */
import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';

interface MainLayoutProps {
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { to: '/', label: 'Home' },
  { to: '/city-situation', label: 'City View' },
  { to: '/issues', label: 'Issues' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/community', label: 'Community' },
  { to: '/profile', label: 'Profile' },
];

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const location = useLocation();

  return (
    <div className="min-h-screen" style={{ background: 'var(--ground)' }}>
      {/* ── Top Bar ──────────────────────────────────────────────────────── */}
      <header className="overlooker-topbar">
        <div className="flex items-center gap-4">
          {/* Logo mark */}
          <div
            className="w-8 h-8 rounded-md border-2 border-ink flex items-center justify-center font-display text-sm"
            style={{ background: 'var(--wine)', color: 'var(--on-wine)' }}
          >
            CC
          </div>
          <span className="font-display text-sm text-ink hidden sm:block">CivicConnect</span>
          {/* OVERLOOKER chip */}
          <span className="cc-chip text-[9px] bg-lime-tint font-mono font-semibold tracking-wider uppercase">
            OVERLOOKER
          </span>
        </div>

        {/* Pill navigation */}
        <nav className="overlooker-pill-nav hidden md:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `overlooker-pill-link ${isActive ? 'overlooker-pill-link-active' : ''}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Read-only badge */}
        <div className="flex items-center gap-3">
          <span className="cc-chip cc-chip-dashed text-[9px] text-muted font-mono">
            Read Only
          </span>
        </div>
      </header>

      {/* ── Mobile bottom navigation ────────────────────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 overlooker-topbar border-b-0 border-t-2 border-ink h-auto py-2 px-2 gap-0 justify-around flex-nowrap">
        {NAV_ITEMS.slice(0, 5).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `text-[10px] font-mono py-1 px-2 rounded-md transition-colors ${isActive ? 'bg-ink text-on-wine font-semibold' : 'text-muted'}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* ── Main content with route transitions ─────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="overlooker-main pb-20 md:pb-10"
        >
          {children}
        </motion.main>
      </AnimatePresence>
    </div>
  );
};

export default MainLayout;