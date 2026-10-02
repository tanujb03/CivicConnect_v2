import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Heart, ChevronDown, TrendingUp, Clock, Users, MapPin } from 'lucide-react';
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
      setLikedIssues(likedIssues.filter(id => id !== issueId));
      setLocalUpvotes(prev => ({ ...prev, [issueId]: prev[issueId] - 1 }));
    } else {
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

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-blue-50 text-blue-700 border border-blue-100';
      case 'in-progress': return 'bg-amber-50 text-amber-700 border border-amber-100';
      case 'resolved': return 'bg-emerald-50 text-emerald-700 border border-emerald-100';
      default: return 'bg-gray-50 text-gray-700 border border-gray-100';
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
    <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec] pb-24">
      {/* Premium Header */}
      <div className="header-civic text-white px-5 pt-6 pb-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
              <Users className="w-4 h-4 text-white/80" />
            </div>
            <h1 className="text-xl font-extrabold tracking-tight">Community</h1>
          </div>
          <div className="relative">
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
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-white/10 backdrop-blur-sm rounded-xl p-1 border border-white/10">
          <button
            onClick={() => setActiveTab('trending')}
            className={`flex items-center justify-center gap-1.5 flex-1 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300 ${
              activeTab === 'trending'
                ? 'bg-white text-emerald-700 shadow-sm'
                : 'text-white/70 hover:text-white'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Trending</span>
          </button>
          <button
            onClick={() => setActiveTab('latest')}
            className={`flex items-center justify-center gap-1.5 flex-1 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300 ${
              activeTab === 'latest'
                ? 'bg-white text-emerald-700 shadow-sm'
                : 'text-white/70 hover:text-white'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Latest</span>
          </button>
        </div>
      </div>

      {/* Issues List */}
      <div className="px-5 pt-5 space-y-3">
        {sortedIssues.map((issue, i) => {
          const isLiked = likedIssues.includes(issue.id);
          return (
            <motion.div
              key={issue.id}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: i * 0.04 }}
              className="glass-card overflow-hidden hover:shadow-civic transition-all duration-300 group"
            >
              {/* Issue Photo */}
              {issue.image && (
                <div className="w-full relative overflow-hidden">
                  <img
                    src={issue.image}
                    alt={issue.title}
                    className="w-full h-44 object-cover cursor-pointer group-hover:scale-105 transition-transform duration-700"
                    onClick={() => navigate(`/issue/${issue.id}`)}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
                </div>
              )}

              {/* Issue Details */}
              <div className="p-4 flex gap-3.5">
                <div className="flex-shrink-0 mt-0.5">
                  <DepartmentIcon category={issue.category} size="lg" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <h3
                      className="font-semibold text-gray-800 text-[14px] cursor-pointer hover:text-emerald-700 transition-colors line-clamp-2 leading-snug"
                      onClick={() => navigate(`/issue/${issue.id}`)}
                    >
                      {issue.title}
                    </h3>
                    <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-lg shrink-0 ${getStatusStyle(issue.status)}`}>
                      {getStatusText(issue.status)}
                    </span>
                  </div>
                  
                  <p className="text-xs text-gray-400 font-medium mb-1.5">
                    {new Date(issue.date).toLocaleDateString()}
                  </p>
                  
                  {issue.landmark && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-400">
                      <MapPin className="w-3 h-3" />
                      <span>{issue.landmark}</span>
                    </div>
                  )}
                </div>

                {/* Upvote button */}
                <div className="flex-shrink-0 flex flex-col items-center gap-0.5">
                  <motion.button
                    onClick={() => handleToggleUpvote(issue.id)}
                    whileTap={{ scale: 1.3 }}
                    className={`p-2.5 rounded-xl transition-all duration-300 ${
                      isLiked ? 'bg-red-50 shadow-sm' : 'hover:bg-red-50'
                    }`}
                  >
                    <Heart
                      className={`w-5 h-5 transition-all duration-300 ${
                        isLiked ? 'text-red-500 fill-red-500 scale-110' : 'text-gray-300'
                      }`}
                    />
                  </motion.button>
                  <span className={`text-xs font-bold transition-colors ${isLiked ? 'text-red-500' : 'text-gray-400'}`}>
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