import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Edit, Trash2, Heart, MapPin, Play, Pause } from 'lucide-react';
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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Issue not found</p>
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
        // Implement delete from communityPosts if needed
        navigate('/community');
      }
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-red-100 text-red-800';
      case 'in-progress': return 'bg-yellow-100 text-yellow-800';
      case 'resolved': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
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
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm p-4">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <h1 className="text-lg font-semibold text-gray-800">Issue Details</h1>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* Image */}
        {issue.image && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="w-full h-full rounded-xl overflow-hidden shadow-sm"
          >
            <img src={issue.image} alt={issue.title} className="w-full h-full object-cover" />
          </motion.div>
        )}

        {/* Info Card */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-xl shadow-sm p-6 space-y-4"
        >
          {/* Title and Category */}
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h2 className="text-xl font-bold text-gray-800 mb-2">{issue.title}</h2>
              {'category' in issue && issue.category && (
                <div className="flex items-center space-x-2">
                  <DepartmentIcon category={issue.category} size="sm" />
                  <span className="text-sm text-gray-600 capitalize">{issue.category}</span>
                </div>
              )}
            </div>
            {'status' in issue && issue.status && (
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(issue.status)}`}>
                {issue.status.replace('-', ' ').toUpperCase()}
              </div>
            )}
          </div>

          {/* Metadata */}
          {'date' in issue && 'category' in issue && 'status' in issue && (
            <div className="grid grid-cols-2 gap-4 py-4 border-t border-gray-100">
              <div>
                <p className="text-sm text-gray-500">Last Updated</p>
                <p className="font-medium text-gray-800">{new Date(issue.date).toLocaleDateString()}</p>
              </div>
              {'category' in issue && 'status' in issue && (
                <div>
                  <p className="text-sm text-gray-500">Expected Resolution</p>
                  <p className="font-medium text-gray-800">{getExpectedResolution(issue.category, issue.status)}</p>
                </div>
              )}
            </div>
          )}

          {/* Description */}
          {'description' in issue && issue.description && (
            <div className="border-t border-gray-100 pt-4">
              <p className="text-sm text-gray-500 mb-2">Description</p>
              <p className="text-gray-800 leading-relaxed">{issue.description}</p>
            </div>
          )}

          {/* Audio */}
          {'audio' in issue && issue.audio && (
            <div className="border-t border-gray-100 pt-4">
              <p className="text-sm text-gray-500 mb-3">Audio Recording</p>
              <div className="flex items-center space-x-4 bg-gray-50 rounded-lg p-4">
                <button
                  onClick={toggleAudio}
                  className="flex items-center justify-center w-10 h-10 bg-green-500 text-white rounded-full hover:bg-green-600 transition-colors"
                >
                  {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                </button>
                <div className="flex-1">
                  <div className="w-full bg-gray-300 rounded-full h-2">
                    <div className="bg-green-500 h-2 rounded-full w-1/3"></div>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">0:23 / 1:00</p>
                </div>
              </div>
            </div>
          )}

          {/* Landmark */}
          {'landmark' in issue && issue.landmark && (
            <div className="border-t border-gray-100 pt-4">
              <div className="flex items-center space-x-2">
                <MapPin className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-500">Landmark:</span>
                <span className="text-gray-800">{issue.landmark}</span>
              </div>
            </div>
          )}
        </motion.div>

        {/* Actions */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-xl shadow-sm p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0"
        >
          <div className="flex items-center space-x-3">
            <button
              onClick={handleUpvote}
              className="flex items-center space-x-2 px-4 py-2 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
            >
              <Heart className="w-5 h-5 text-red-500" />
              <span className="text-red-600 font-medium">
                {'upvotes' in issue ? 'Upvote' : likedByUser ? 'Liked' : 'Like'}
              </span>
            </button>
            <span className="text-gray-600">{likesCount} people support this</span>
          </div>

          {isOwnIssue && (
            <div className="flex space-x-3">
              <button
                onClick={() => navigate(`/report?edit=${issue.id}`)}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg transition-colors"
              >
                <Edit className="w-4 h-4" />
                <span>Edit</span>
              </button>
              <button
                onClick={handleDelete}
                className="flex items-center space-x-2 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg transition-colors"
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
