import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronDown, Filter, RotateCcw, FileText, MapPin, Calendar } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import BottomNavigation from './BottomNavigation';
import { DepartmentIcon } from './DepartmentIcon';

// Define Issue type
type IssueType = {
  id: string;
  title: string;
  description?: string;
  category: string;
  status: string;
  date: string;
  image?: string;
  audio?: string;
  landmark?: string;
  upvotes?: number;
  userId?: string;
  location?: { lat: number; lng: number };
};

// Mock issues (to fill up to 5 if user has fewer)
const mockIssues: IssueType[] = [
  { id: 'm1', title: 'Pothole on Main St', category: 'roads', status: 'submitted', date: '2025-09-19', landmark: 'Near City Hall' },
  { id: 'm2', title: 'Street light not working', category: 'lighting', status: 'in-progress', date: '2025-09-18', landmark: 'Park Avenue' },
  { id: 'm3', title: 'Water leakage', category: 'water', status: 'resolved', date: '2025-09-17', landmark: 'Lakeview Rd' },
  { id: 'm4', title: 'Overflowing garbage', category: 'sanitation', status: 'submitted', date: '2025-09-16', landmark: 'Market Street' },
  { id: 'm5', title: 'Broken sidewalk', category: 'roads', status: 'in-progress', date: '2025-09-15', landmark: '5th Avenue' },
];

const MyReports: React.FC = () => {
  const navigate = useNavigate();
  const { state, dispatch } = useApp();

  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateSort, setDateSort] = useState<'asc' | 'desc'>('desc');

  // Only the user's own issues
  const userIssues = state.issues.filter(issue => issue.userId === state.user?.id);

  // Ensure at least 5 reports by filling from mockIssues
  const combined: IssueType[] = [...userIssues];
  if (combined.length < 5) {
    const needed = 5 - combined.length;
    combined.push(
      ...mockIssues
        .slice(0, needed)
        .map(issue => ({ ...issue, userId: state.user?.id || '1', description: '', upvotes: 0, location: { lat: 23.3441, lng: 85.3096 } }))
    );
  }

  // Apply filters and sorting
  const filteredIssues = combined
    .filter(issue => categoryFilter === 'all' || issue.category === categoryFilter)
    .filter(issue => statusFilter === 'all' || issue.status === statusFilter)
    .sort((a, b) => {
      const dateA = new Date(a.date).getTime();
      const dateB = new Date(b.date).getTime();
      return dateSort === 'desc' ? dateB - dateA : dateA - dateB;
    });

  const handleReopenIssue = (issueId: string) => {
    dispatch({
      type: 'UPDATE_ISSUE',
      payload: {
        id: issueId,
        updates: { status: 'submitted', date: new Date().toISOString().split('T')[0] }
      }
    });
  };

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-blue-50 text-blue-700 border border-blue-100';
      case 'in-progress': return 'bg-amber-50 text-amber-700 border border-amber-100';
      case 'resolved': return 'bg-emerald-50 text-emerald-700 border border-emerald-100';
      default: return 'bg-gray-50 text-gray-700 border border-gray-100';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec] pb-24">
      {/* Premium Header */}
      <div className="header-civic text-white px-5 pt-6 pb-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
            <FileText className="w-4 h-4 text-white/80" />
          </div>
          <h1 className="text-xl font-extrabold tracking-tight">My Reports</h1>
          <span className="ml-auto bg-white/15 backdrop-blur-sm px-2.5 py-1 rounded-lg text-xs font-semibold border border-white/10">
            {filteredIssues.length} total
          </span>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
          <div className="relative flex-shrink-0">
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="appearance-none bg-white/15 backdrop-blur-sm border border-white/10 rounded-xl px-3 py-2 pr-7 text-xs text-white font-medium focus:outline-none focus:ring-1 focus:ring-white/30"
            >
              <option value="all" className="text-gray-800">All Categories</option>
              <option value="roads" className="text-gray-800">Roads</option>
              <option value="sanitation" className="text-gray-800">Sanitation</option>
              <option value="water" className="text-gray-800">Water</option>
              <option value="lighting" className="text-gray-800">Lighting</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-white/50 pointer-events-none" />
          </div>

          <div className="relative flex-shrink-0">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="appearance-none bg-white/15 backdrop-blur-sm border border-white/10 rounded-xl px-3 py-2 pr-7 text-xs text-white font-medium focus:outline-none focus:ring-1 focus:ring-white/30"
            >
              <option value="all" className="text-gray-800">All Status</option>
              <option value="submitted" className="text-gray-800">Submitted</option>
              <option value="in-progress" className="text-gray-800">In Progress</option>
              <option value="resolved" className="text-gray-800">Resolved</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-white/50 pointer-events-none" />
          </div>

          <button
            onClick={() => setDateSort(dateSort === 'desc' ? 'asc' : 'desc')}
            className="flex items-center gap-1.5 bg-white/15 backdrop-blur-sm border border-white/10 rounded-xl px-3 py-2 text-xs text-white font-medium hover:bg-white/20 transition-colors flex-shrink-0"
          >
            <Calendar className="w-3 h-3" />
            <span>Date</span>
            <ChevronDown className={`w-3 h-3 transition-transform duration-300 ${dateSort === 'asc' ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Issues List */}
      <div className="px-5 pt-5 space-y-3">
        {filteredIssues.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gray-100 flex items-center justify-center">
              <Filter className="w-7 h-7 text-gray-400" />
            </div>
            <p className="text-gray-500 font-medium">No reports found</p>
            <p className="text-xs text-gray-400 mt-1">Try adjusting your filters</p>
          </div>
        ) : (
          filteredIssues.map((issue, i) => (
            <motion.div
              key={issue.id}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: i * 0.05 }}
              className="glass-card p-4 hover:shadow-civic transition-all duration-300 cursor-pointer group"
              onClick={() => navigate(`/issue/${issue.id}`)}
            >
              <div className="flex gap-3.5">
                {/* Issue Image / Icon */}
                <div className="w-16 h-16 bg-gray-50 rounded-xl overflow-hidden flex-shrink-0 flex items-center justify-center group-hover:bg-emerald-50 transition-colors">
                  {issue.image ? (
                    <img src={issue.image} alt={issue.title} className="w-full h-full object-cover" />
                  ) : (
                    <DepartmentIcon category={issue.category} size="md" />
                  )}
                </div>

                {/* Issue Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <h3 className="font-semibold text-gray-800 text-[14px] truncate group-hover:text-emerald-700 transition-colors">
                      {issue.title}
                    </h3>
                    <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-lg shrink-0 ${getStatusStyle(issue.status)}`}>
                      {issue.status.replace('-', ' ').toUpperCase()}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <Calendar className="w-3 h-3" />
                    <span className="font-medium">{issue.date}</span>
                    <span className="text-gray-200">•</span>
                    <DepartmentIcon category={issue.category} size="sm" />
                    <span className="capitalize">{issue.category}</span>
                  </div>

                  {issue.landmark && (
                    <div className="flex items-center gap-1.5 mt-1.5 text-xs text-gray-400">
                      <MapPin className="w-3 h-3" />
                      <span>{issue.landmark}</span>
                    </div>
                  )}

                  {/* Re-open button */}
                  {issue.status === 'resolved' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleReopenIssue(issue.id); }}
                      className="flex items-center gap-1.5 mt-2.5 text-xs text-amber-600 hover:text-amber-700 font-semibold transition-colors"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Re-open Issue</span>
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          ))
        )}
      </div>

      <BottomNavigation />
    </div>
  );
};

export default MyReports;