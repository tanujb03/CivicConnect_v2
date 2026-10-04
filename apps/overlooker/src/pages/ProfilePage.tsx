/**
 * O06 — Profile
 * Overlooker's profile page with personal info, jurisdiction details,
 * activity log, and session management.
 *
 * Read-only with only logout action available.
 */
import React from 'react';
import { User, MapPin, Shield, Clock, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const activityLog = [
  { action: 'Viewed W12 heatmap detail', time: '10 min ago' },
  { action: 'Accessed city situation report', time: '25 min ago' },
  { action: 'Opened case CC-1042 detail', time: '1h ago' },
  { action: 'Reviewed analytics dashboard', time: '2h ago' },
  { action: 'Logged in', time: '3h ago' },
];

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const userName = localStorage.getItem('civic_user_name') || 'Overlooker';
  const jurisdiction = localStorage.getItem('civic_user_jurisdiction') || 'ranchi';

  const handleLogout = () => {
    localStorage.removeItem('civic_auth_token');
    localStorage.removeItem('civic_user_role');
    localStorage.removeItem('civic_user_name');
    localStorage.removeItem('civic_user_jurisdiction');
    window.location.href = '/login';
  };

  const jurisdictionNames: Record<string, string> = {
    ranchi: 'Ranchi Municipal Corporation',
    jamshedpur: 'Jamshedpur Municipal',
    dhanbad: 'Dhanbad Municipal',
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">O06</div>
        <h1 className="cc-title cc-headline-pop">Profile</h1>
      </div>

      {/* Profile card */}
      <div className="cc-card p-6 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <div className="flex items-start gap-4">
          <div
            className="w-16 h-16 rounded-md border-2 border-ink flex items-center justify-center font-display text-2xl shrink-0"
            style={{ background: 'var(--wine)', color: 'var(--on-wine)' }}
          >
            {userName.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1">
            <h2 className="font-display text-xl text-ink">{userName}</h2>
            <div className="flex items-center gap-2 mt-2">
              <span className="cc-chip text-[9px] bg-lime-tint font-mono tracking-wider uppercase">OVERLOOKER</span>
              <span className="cc-chip cc-chip-dashed text-[9px] text-muted">Read Only</span>
            </div>
          </div>
          <button
            className="cc-btn cc-btn-outline text-sm"
            onClick={handleLogout}
            style={{ borderColor: 'var(--fire)', color: 'var(--fire)' }}
          >
            <LogOut className="h-4 w-4" /> Logout
          </button>
        </div>
      </div>

      {/* Info grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="cc-card p-5 cc-card-lift cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
              <MapPin className="h-3.5 w-3.5 text-ink" />
            </div>
            <h3 className="font-display text-sm text-ink">Jurisdiction</h3>
          </div>
          <p className="text-sm font-medium text-ink">{jurisdictionNames[jurisdiction] || jurisdiction}</p>
          <p className="text-xs font-mono text-muted mt-1">All wards within jurisdiction</p>
        </div>

        <div className="cc-card p-5 cc-card-lift cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
              <Shield className="h-3.5 w-3.5 text-ink" />
            </div>
            <h3 className="font-display text-sm text-ink">Access Level</h3>
          </div>
          <p className="text-sm font-medium text-ink">Read-only</p>
          <p className="text-xs font-mono text-muted mt-1">View cases, analytics, and city status</p>
        </div>
      </div>

      {/* Activity log */}
      <div className="cc-card cc-fade-up" style={{ '--stagger-index': 3 } as React.CSSProperties}>
        <div className="px-5 py-3 border-b-2 border-ink">
          <h3 className="font-display text-sm text-ink flex items-center gap-2">
            <Clock className="h-4 w-4" style={{ color: 'var(--wine)' }} />
            Recent Activity
          </h3>
        </div>
        <div className="p-5">
          <div className="cc-timeline">
            {activityLog.map((entry, i) => (
              <div
                key={i}
                className="cc-timeline-event cc-fade-up"
                style={{ '--stagger-index': i } as React.CSSProperties}
              >
                <p className="text-sm text-ink">{entry.action}</p>
                <p className="text-[10px] font-mono text-muted mt-1">{entry.time}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;