import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Edit, Trash2, Heart, MapPin, Play, Pause, Calendar, Clock, Tag } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { DepartmentIcon } from './DepartmentIcon';

const IssueDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { state, dispatch } = useApp();
  const [isPlaying, setIsPlaying] = useState(false);

  // Find issue or community post
  const issue =
    state.issues.find(i => i.id === id) ||
    state.communityPosts.find(p => p.id === id);

  if (!issue) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec] flex flex-col items-center justify-center px-6">
        <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
          <Tag className="w-7 h-7 text-gray-400" />
        </div>
        <p className="text-gray-500 font-semibold">Issue not found</p>
        <button onClick={() => navigate(-1)} className="mt-4 text-emerald-600 text-sm font-semibold hover:text-emerald-700">← Go back</button>
      </div>
    );
  }

  const isOwnIssue = issue.userId === state.user?.id;
  const likedByUser = 'likes' in issue ? issue.likes.includes(state.user?.id || '') : false;
  const likesCount = 'upvotes' in issue ? issue.upvotes : 'likes' in issue ? issue.likes.length : 0;

  const handleUpvote = () => {
    if ('upvotes' in issue) {
      dispatch({ type: 'UPVOTE_ISSUE', payload: issue.id });
    } else if ('likes' in issue) {
      dispatch({ type: 'TOGGLE_LIKE', payload: { postId: issue.id } });
    }
  };

  const handleDelete = () => {
    if ('upvotes' in issue) {
      if (window.confirm('Are you sure you want to delete this issue?')) {
        dispatch({ type: 'DELETE_ISSUE', payload: issue.id });
        navigate('/my-reports');
      }
    } else if ('likes' in issue) {
      if (window.confirm('Are you sure you want to delete this post?')) {
        navigate('/community');
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

  const getExpectedResolution = (category: string, status: string) => {
    const timelines: Record<string, string> = {
      roads: '7-14 days',
      sanitation: '1-3 days',
      water: '2-5 days',
      lighting: '3-7 days',
    };
    if (status === 'resolved') return 'Completed';
    return timelines[category] || '5-10 days';
  };

  const toggleAudio = () => setIsPlaying(!isPlaying);

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec]">
      {/* Sticky Header */}
      <div className="bg-white/80 backdrop-blur-xl border-b border-emerald-100/50 px-5 py-4 sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="w-10 h-10 rounded-xl bg-gray-50 hover:bg-gray-100 flex items-center justify-center transition-all duration-300"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <h1 className="text-lg font-bold text-gray-900">Issue Details</h1>
        </div>
      </div>

      <div className="px-5 pt-4 pb-8 space-y-4">
        {/* Image */}
        {issue.image && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="w-full rounded-2xl overflow-hidden shadow-glass"
          >
            <img src={issue.image} alt={issue.title} className="w-full h-56 object-cover" />
          </motion.div>
        )}

        {/* Info Card */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-5 space-y-4"
        >
          {/* Title and Status */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <h2 className="text-xl font-extrabold text-gray-900 tracking-tight mb-2">{issue.title}</h2>
              {'category' in issue && issue.category && (
                <div className="flex items-center gap-2">
                  <DepartmentIcon category={issue.category} size="sm" />
                  <span className="text-sm text-gray-500 capitalize font-medium">{issue.category}</span>
                </div>
              )}
            </div>
            {'status' in issue && issue.status && (
              <span className={`px-3 py-1 rounded-lg text-xs font-semibold shrink-0 ${getStatusStyle(issue.status)}`}>
                {issue.status.replace('-', ' ').toUpperCase()}
              </span>
            )}
          </div>

          {/* Metadata Grid */}
          {'date' in issue && 'category' in issue && 'status' in issue && (
            <div className="grid grid-cols-2 gap-3 py-3 border-t border-gray-100/60">
              <div className="bg-gray-50/80 rounded-xl p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Calendar className="w-3 h-3 text-gray-400" />
                  <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">Last Updated</p>
                </div>
                <p className="font-bold text-gray-800 text-sm">{new Date(issue.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</p>
              </div>
              {'category' in issue && 'status' in issue && (
                <div className="bg-gray-50/80 rounded-xl p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Clock className="w-3 h-3 text-gray-400" />
                    <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">Est. Resolution</p>
                  </div>
                  <p className="font-bold text-gray-800 text-sm">{getExpectedResolution(issue.category, issue.status)}</p>
                </div>
              )}
            </div>
          )}

          {/* Description */}
          {'description' in issue && issue.description && (
            <div className="border-t border-gray-100/60 pt-4">
              <p className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-2">Description</p>
              <p className="text-gray-700 leading-relaxed text-sm">{issue.description}</p>
            </div>
          )}

          {/* Audio */}
          {'audio' in issue && issue.audio && (
            <div className="border-t border-gray-100/60 pt-4">
              <p className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-3">Audio Recording</p>
              <div className="flex items-center gap-3 bg-emerald-50/50 rounded-xl p-3.5">
                <button
                  onClick={toggleAudio}
                  className="flex items-center justify-center w-10 h-10 rounded-xl text-white shrink-0 transition-all duration-300"
                  style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)', boxShadow: '0 4px 12px rgba(22,163,74,0.25)' }}
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
                </button>
                <div className="flex-1">
                  <div className="w-full bg-emerald-200/50 rounded-full h-1.5">
                    <div className="bg-emerald-500 h-1.5 rounded-full w-1/3 transition-all duration-300"></div>
                  </div>
                  <p className="text-xs text-gray-500 mt-1.5 font-medium">0:23 / 1:00</p>
                </div>
              </div>
            </div>
          )}

          {/* Landmark */}
          {'landmark' in issue && issue.landmark && (
            <div className="border-t border-gray-100/60 pt-4">
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-emerald-500" />
                <span className="text-sm text-gray-500 font-medium">Landmark:</span>
                <span className="text-sm text-gray-800 font-semibold">{issue.landmark}</span>
              </div>
            </div>
          )}
        </motion.div>

        {/* Actions */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-5 space-y-4"
        >
          <div className="flex items-center justify-between">
            <motion.button
              onClick={handleUpvote}
              whileTap={{ scale: 1.1 }}
              className="flex items-center gap-2 px-5 py-2.5 bg-rose-50 hover:bg-rose-100 rounded-xl transition-all duration-300 border border-rose-100/50"
            >
              <Heart className={`w-5 h-5 transition-all ${likedByUser ? 'text-rose-500 fill-rose-500' : 'text-rose-400'}`} />
              <span className="text-rose-600 font-semibold text-sm">
                {'upvotes' in issue ? 'Upvote' : likedByUser ? 'Liked' : 'Like'}
              </span>
            </motion.button>
            <span className="text-sm text-gray-500 font-medium">{likesCount} people support this</span>
          </div>

          {isOwnIssue && (
            <div className="flex gap-3 pt-2 border-t border-gray-100/60">
              <button
                onClick={() => navigate(`/report?edit=${issue.id}`)}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-xl transition-all duration-300 font-semibold text-sm border border-blue-100/50"
              >
                <Edit className="w-4 h-4" />
                <span>Edit</span>
              </button>
              <button
                onClick={handleDelete}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-red-50 hover:bg-red-100 text-red-600 rounded-xl transition-all duration-300 font-semibold text-sm border border-red-100/50"
              >
                <Trash2 className="w-4 h-4" />
                <span>Delete</span>
              </button>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
};

export default IssueDetail;
