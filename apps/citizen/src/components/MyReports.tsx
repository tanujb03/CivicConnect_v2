import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronDown, Filter, RotateCcw } from 'lucide-react';
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-red-100 text-red-800';
      case 'in-progress': return 'bg-yellow-100 text-yellow-800';
      case 'resolved': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] shadow-sm p-4">
        <h1 className="text-xl font-bold text-white">My Reports</h1>

        {/* Filters and View Drafts button */}
        <div className="flex items-center justify-between mt-4 overflow-x-auto pb-2">
          <div className="flex space-x-2">
            {/* Category Filter */}
            <div className="relative flex-shrink-0">
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="appearance-none bg-white border border-gray-300 rounded-lg px-2 py-1 text-xs focus:ring-2 focus:ring-green-500 focus:border-green-500"
              >
                <option value="all">Categories</option>
                <option value="roads">Roads</option>
                <option value="sanitation">Sanitation</option>
                <option value="water">Water</option>
                <option value="lighting">Lighting</option>
              </select>
              <ChevronDown className="absolute right-1.5 top-1/2 transform -translate-y-1/2 w-3 h-3 text-gray-500" />
            </div>

            {/* Status Filter */}
            <div className="relative flex-shrink-0">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="appearance-none bg-white border border-gray-300 rounded-lg px-2 py-1 text-xs focus:ring-2 focus:ring-green-500 focus:border-green-500"
              >
                <option value="all">Status</option>
                <option value="submitted">Submitted</option>
                <option value="in-progress">In Progress</option>
                <option value="resolved">Resolved</option>
              </select>
              <ChevronDown className="absolute right-1.5 top-1/2 transform -translate-y-1/2 w-3 h-3 text-gray-500" />
            </div>

            {/* Date Sort */}
            <button
              onClick={() => setDateSort(dateSort === 'desc' ? 'asc' : 'desc')}
              className="flex items-center space-x-1 bg-white border border-gray-300 rounded-lg px-2 py-1 text-xs hover:bg-gray-200 transition-colors flex-shrink-0"
            >
              <span>Date</span>
              <ChevronDown className={`w-3 h-3 transition-transform ${dateSort === 'asc' ? 'rotate-180' : ''}`} />
            </button>
          </div>
          
          <button
            onClick={() => {}} // This button has no functionality, it's for representation.
            className="px-2 py-1 bg-white text-gray-800 rounded-full text-xs font-medium hover:bg-gray-200 transition-colors flex-shrink-0"
          >
            View Drafts
          </button>
        </div>
      </div>

      {/* Issues List */}
      <div className="p-4 space-y-4">
        {filteredIssues.length === 0 ? (
          <div className="text-center py-12">
            <Filter className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No reports found matching your filters</p>
          </div>
        ) : (
          filteredIssues.map((issue) => (
            <motion.div
              key={issue.id}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex space-x-4">
                {/* Issue Image */}
                <div className="w-20 h-20 bg-gray-200 rounded-lg overflow-hidden flex-shrink-0">
                  {issue.image ? (
                    <img
                      src={issue.image}
                      alt={issue.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <DepartmentIcon category={issue.category} size="md" />
                    </div>
                  )}
                </div>

                {/* Issue Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between mb-2">
                    <h3
                      className="font-medium text-gray-800 truncate cursor-pointer hover:text-green-600"
                      onClick={() => navigate(`/issue/${issue.id}`)}
                    >
                      {issue.title}
                    </h3>
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(issue.status)}`}>
                      {issue.status.replace('-', ' ').toUpperCase()}
                    </span>
                  </div>

                  <p className="text-sm text-gray-600 mb-2">{issue.date}</p>

                  <div className="flex items-center space-x-2">
                    <DepartmentIcon category={issue.category} size="sm" />
                    <span className="text-xs text-gray-500 capitalize">{issue.category}</span>
                    {issue.landmark && (
                      <>
                        <span className="text-gray-300">•</span>
                        <span className="text-xs text-gray-500">{issue.landmark}</span>
                      </>
                    )}
                  </div>

                  {/* Actions */}
                  {issue.status === 'resolved' && (
                    <button
                      onClick={() => handleReopenIssue(issue.id)}
                      className="flex items-center space-x-1 mt-3 text-sm text-orange-600 hover:text-orange-700"
                    >
                      <RotateCcw className="w-4 h-4" />
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