
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Heart, ChevronDown, TrendingUp, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import BottomNavigation from './BottomNavigation';
import { DepartmentIcon } from './DepartmentIcon';

const Community: React.FC = () => {
  const navigate = useNavigate();
  const { state, dispatch } = useApp();
  const [activeTab, setActiveTab] = useState<'trending' | 'latest'>('trending');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  // Track liked issues
  const [likedIssues, setLikedIssues] = useState<string[]>([]);
  // Track upvotes locally
  const [localUpvotes, setLocalUpvotes] = useState<Record<string, number>>(
    () => Object.fromEntries(state.issues.map(issue => [issue.id, issue.upvotes]))
  );

  const filteredIssues = state.issues
    .filter(issue => categoryFilter === 'all' || issue.category === categoryFilter);

  const sortedIssues = activeTab === 'trending'
    ? [...filteredIssues].sort((a, b) => localUpvotes[b.id] - localUpvotes[a.id]).slice(0, 15)
    : [...filteredIssues].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const handleToggleUpvote = (issueId: string) => {
    const isLiked = likedIssues.includes(issueId);

    if (isLiked) {
      // Remove like
      setLikedIssues(likedIssues.filter(id => id !== issueId));
      setLocalUpvotes(prev => ({ ...prev, [issueId]: prev[issueId] - 1 }));
    } else {
      // Add like
      setLikedIssues([...likedIssues, issueId]);
      setLocalUpvotes(prev => ({ ...prev, [issueId]: prev[issueId] + 1 }));
      dispatch({ type: 'UPVOTE_ISSUE', payload: issueId });

      const issue = state.issues.find(i => i.id === issueId);
      if (issue && localUpvotes[issueId] + 1 >= 5 && issue.userId !== state.user?.id) {
        dispatch({
          type: 'ADD_NOTIFICATION',
          payload: {
            id: Date.now().toString(),
            title: 'Issue Getting Attention',
            description: `"${issue.title}" has received 5+ upvotes`,
            date: new Date().toISOString(),
            type: 'info'
          }
        });
      }
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-red-500';
      case 'in-progress': return 'bg-yellow-500';
      case 'resolved': return 'bg-green-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'submitted': return 'Submitted';
      case 'in-progress': return 'In Progress';
      case 'resolved': return 'Resolved';
      default: return status;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] shadow-sm p-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold text-white">Community</h1>
          <div className="relative">
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="appearance-none bg-green-100 border border-gray-300 rounded-lg px-4 py-2 pr-8 text-sm focus:ring-2 focus:ring-green-500 focus:border-green-500"
            >
              <option value="all">All Categories</option>
              <option value="roads">Roads</option>
              <option value="sanitation">Sanitation</option>
              <option value="water">Water</option>
              <option value="lighting">Lighting</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-500" />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex">
          <button
            onClick={() => setActiveTab('trending')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'trending'
                ? 'bg-green-100 text-green-600'
                : 'text-black hover:text-green-600'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            <span>Trending</span>
          </button>
          <button
            onClick={() => setActiveTab('latest')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'latest'
                ? 'bg-green-100 text-green-600'
                : 'text-black hover:text-green-600'
            }`}
          >
            <Clock className="w-4 h-4" />
            <span>Latest</span>
          </button>
        </div>
      </div>

      {/* Issues List */}
      <div className="p-4 space-y-4">
        {sortedIssues.map((issue) => {
          const isLiked = likedIssues.includes(issue.id);
          return (
            <motion.div
              key={issue.id}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md transition-shadow"
            >
              {/* Issue Photo */}
              {issue.image && (
                <div className="w-full">
                  <img
                    src={issue.image}
                    alt={issue.title}
                    className="w-full h-48 object-cover cursor-pointer hover:opacity-95 transition-opacity"
                    onClick={() => navigate(`/issue/${issue.id}`)}
                  />
                </div>
              )}

              {/* Issue Details */}
              <div className="p-4 flex space-x-4">
                <div className="flex-shrink-0">
                  <DepartmentIcon category={issue.category} size="lg" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between mb-2">
                    <h3
                      className="font-medium text-gray-800 cursor-pointer hover:text-green-600 line-clamp-2"
                      onClick={() => navigate(`/issue/${issue.id}`)}
                    >
                      {issue.title}
                    </h3>
                    <div className={`px-2 py-1 rounded-full text-xs font-medium text-white ml-2 ${getStatusColor(issue.status)}`}>
                      {getStatusText(issue.status)}
                    </div>
                  </div>
                  
                  <p className="text-sm text-gray-600 mb-3">
                    Last updated: {new Date(issue.date).toLocaleDateString()}
                  </p>
                  
                  {issue.landmark && (
                    <p className="text-xs text-gray-500 mb-3">{issue.landmark}</p>
                  )}

                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500 capitalize">
                      {issue.category}
                    </span>
                  </div>
                </div>

                <div className="flex-shrink-0 flex flex-col items-center space-y-1">
                  <button
                    onClick={() => handleToggleUpvote(issue.id)}
                    className="p-2 rounded-full hover:bg-red-50 transition-colors group"
                  >
                    <Heart
                      className={`w-5 h-5 transition-transform group-hover:scale-110 ${
                        isLiked ? 'text-red-600 fill-red-600' : 'text-red-500'
                      }`}
                    />
                  </button>
                  <span className="text-xs font-medium text-gray-600">
                    {localUpvotes[issue.id]}
                  </span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      <BottomNavigation />
    </div>
  );
};

export default Community;