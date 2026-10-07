/**
 * O05 — Community
 * Read-only community feed showing citizen-reported issues with upvotes,
 * trending topics, and engagement stats.
 *
 * Data: GET /cases?sort=-upvotes&limit=20 (read-only, no mutations).
 */
import React, { useState } from 'react';
import { Search, TrendingUp, MessageSquare, Users, Eye, MapPin, ChevronRight } from 'lucide-react';

interface CommunityIssue {
  id: string;
  title: string;
  description: string;
  category: string;
  location: string;
  ward: string;
  status: string;
  upvotes: number;
  comments: number;
  reportedAt: string;
}

const communityIssues: CommunityIssue[] = [
  { id: '1', title: 'Street food vendors blocking sidewalk', description: 'Multiple food vendors have set up permanent stalls on the main sidewalk.', category: 'Roads', location: 'Main Bazaar, W6', ward: 'W6', status: 'submitted', upvotes: 156, comments: 23, reportedAt: '2d ago' },
  { id: '2', title: 'Children playing in construction site', description: 'An abandoned construction site has become a playground for children.', category: 'Safety', location: 'New Colony, W8', ward: 'W8', status: 'in_progress', upvotes: 89, comments: 12, reportedAt: '3d ago' },
  { id: '3', title: 'Water contamination in residential area', description: 'Residents report yellowish water from taps for the past week.', category: 'Water', location: 'Lake Road, W5', ward: 'W5', status: 'in_progress', upvotes: 234, comments: 45, reportedAt: '5d ago' },
  { id: '4', title: 'Pothole cluster near hospital', description: 'Multiple deep potholes on the approach road to the district hospital.', category: 'Roads', location: 'Hospital Road, W12', ward: 'W12', status: 'submitted', upvotes: 312, comments: 67, reportedAt: '1d ago' },
  { id: '5', title: 'Overflowing garbage bins near park', description: 'Garbage bins in the park area have not been emptied for 4 days.', category: 'Sanitation', location: 'Park Area, W9', ward: 'W9', status: 'resolved', upvotes: 78, comments: 8, reportedAt: '6d ago' },
  { id: '6', title: 'Street lights out in residential lane', description: 'Complete darkness in Lane 4 of the residential block after 7pm.', category: 'Electrical', location: 'Sector 3, W7', ward: 'W7', status: 'submitted', upvotes: 145, comments: 19, reportedAt: '4d ago' },
];

const trendingTopics = [
  { topic: 'Road Safety', cases: 45, trend: '+12%' },
  { topic: 'Water Quality', cases: 28, trend: '+8%' },
  { topic: 'Garbage Collection', cases: 22, trend: '-5%' },
  { topic: 'Street Lighting', cases: 19, trend: '+3%' },
];

const engagementStats = [
  { label: 'Total Reports', value: '1,240', icon: MessageSquare },
  { label: 'Active Citizens', value: '847', icon: Users },
  { label: 'Total Upvotes', value: '8.4K', icon: TrendingUp },
  { label: 'Views This Week', value: '12.3K', icon: Eye },
];

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    submitted: 'bg-lime-tint text-ink',
    in_progress: 'bg-amber text-ink',
    resolved: 'bg-lime text-ink',
  };
  const labels: Record<string, string> = {
    submitted: 'Submitted', in_progress: 'In Progress', resolved: 'Resolved',
  };
  return <span className={`cc-chip text-[10px] ${map[status] ?? ''}`}>{labels[status] ?? status}</span>;
}

const CommunityPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState('upvotes');

  const filtered = communityIssues
    .filter(i => !query || i.title.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => sortBy === 'upvotes' ? b.upvotes - a.upvotes : 0);

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">O05</div>
        <h1 className="cc-title cc-headline-pop">Community</h1>
        <p className="text-xs font-mono text-muted mt-1">Read-only citizen engagement feed</p>
      </div>

      {/* Engagement Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {engagementStats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="cc-kpi-card cc-card-lift cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center bg-lime-tint">
                  <Icon className="h-3.5 w-3.5 text-ink" />
                </div>
              </div>
              <p className="cc-kpi-value text-xl">{stat.value}</p>
              <p className="cc-kpi-label">{stat.label}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main feed */}
        <div className="lg:col-span-2 space-y-4">
          {/* Search + Sort */}
          <div className="cc-card p-4 cc-fade-up" style={{ '--stagger-index': 4 } as React.CSSProperties}>
            <div className="flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                <input
                  type="text"
                  placeholder="Search community reports..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted"
                  style={{ minHeight: '44px' }}
                />
              </div>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-2.5 bg-ground border-2 border-ink rounded-md text-sm text-ink font-medium"
                style={{ minHeight: '44px' }}
              >
                <option value="upvotes">Most Upvoted</option>
                <option value="recent">Most Recent</option>
              </select>
            </div>
          </div>

          {/* Issue cards */}
          {filtered.map((issue, i) => (
            <div
              key={issue.id}
              className="cc-card p-5 cc-card-lift cc-fade-up"
              style={{ '--stagger-index': i + 5 } as React.CSSProperties}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <StatusChip status={issue.status} />
                    <span className="cc-chip text-[9px] py-0 px-1.5 border-muted/30">{issue.category}</span>
                  </div>
                  <h3 className="text-sm font-semibold text-ink mb-1">{issue.title}</h3>
                  <p className="text-xs text-muted line-clamp-2">{issue.description}</p>
                  <div className="flex items-center gap-4 mt-3 text-[10px] font-mono text-muted">
                    <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {issue.location}</span>
                    <span>{issue.reportedAt}</span>
                  </div>
                </div>
                {/* Upvote count */}
                <div className="text-center shrink-0">
                  <div className="w-12 h-12 rounded-md border-2 border-ink flex flex-col items-center justify-center bg-lime-tint">
                    <TrendingUp className="h-3 w-3 text-ink mb-0.5" />
                    <span className="font-display text-sm text-ink">{issue.upvotes}</span>
                  </div>
                  <span className="text-[9px] font-mono text-muted mt-1 block">{issue.comments} comments</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Sidebar: Trending */}
        <div className="lg:col-span-1 space-y-4">
          <div className="cc-card p-5 cc-fade-up" style={{ '--stagger-index': 4 } as React.CSSProperties}>
            <h3 className="font-display text-sm text-ink mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4" style={{ color: 'var(--wine)' }} />
              Trending Topics
            </h3>
            <div className="space-y-3">
              {trendingTopics.map((topic, i) => (
                <div key={topic.topic} className="flex items-center justify-between py-2 border-b border-dot last:border-0 cc-fade-up"
                  style={{ '--stagger-index': i } as React.CSSProperties}>
                  <div>
                    <p className="text-sm font-medium text-ink">{topic.topic}</p>
                    <p className="text-[10px] font-mono text-muted">{topic.cases} cases</p>
                  </div>
                  <span className={`cc-chip text-[9px] py-0 px-1.5 ${topic.trend.startsWith('+') ? 'bg-lime text-ink' : 'bg-dot text-muted'}`}>
                    {topic.trend}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="cc-banner-degraded text-xs cc-fade-up" style={{ '--stagger-index': 5 } as React.CSSProperties}>
            Read-only view. Upvoting and commenting requires the Citizen app.
          </div>
        </div>
      </div>
    </div>
  );
};

export default CommunityPage;
