import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Camera, Mic, Square, MapPin, ChevronDown, RotateCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import BottomNavigation from './BottomNavigation';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import Webcam from 'react-webcam';

const ReportIssue: React.FC = () => {
  const navigate = useNavigate();
  const { dispatch, state } = useApp();

  const webcamRef = useRef<Webcam>(null);

  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: 'roads',
    landmark: '',
    image: null as string | null,
  });

  const [useFrontCamera, setUseFrontCamera] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);

  const {
    isRecording,
    audioUrl,
    recordingTime,
    startRecording,
    stopRecording,
    clearRecording
  } = useAudioRecorder();

  const handleCapture = () => {
    if (webcamRef.current) {
      const imageSrc = webcamRef.current.getScreenshot();
      if (imageSrc) {
        setFormData(prev => ({ ...prev, image: imageSrc }));
        setCameraOpen(false);
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.title || !formData.image) return;

    const newIssue = {
      id: Date.now().toString(),
      title: formData.title,
      description: formData.description,
      category: formData.category as any,
      status: 'submitted' as const,
      date: new Date().toISOString().split('T')[0],
      image: formData.image,
      audio: audioUrl || undefined,
      landmark: formData.landmark || undefined,
      upvotes: 0,
      userId: state.user?.id || '1',
      location: { lat: 23.3441 + Math.random() * 0.01, lng: 85.3096 + Math.random() * 0.01 }
    };

    // Add issue to global state
    dispatch({ type: 'ADD_ISSUE', payload: newIssue });

    // Add notification
    dispatch({
      type: 'ADD_NOTIFICATION',
      payload: {
        id: Date.now().toString(),
        title: 'Issue Reported Successfully',
        description: `Your report "${formData.title}" has been submitted`,
        date: new Date().toISOString(),
        type: 'success'
      }
    });

    // Reset form
    setFormData({ title: '', description: '', category: 'roads', landmark: '', image: null });
    clearRecording();

    // Navigate to My Reports
    navigate('/my-reports');
  };

  const handleSaveDraft = () => {
    // Implement draft saving logic here
    const draftIssue = {
      id: Date.now().toString(),
      title: formData.title,
      description: formData.description,
      category: formData.category as any,
      status: 'draft' as const, // This is a new status for drafts
      date: new Date().toISOString().split('T')[0],
      image: formData.image,
      audio: audioUrl || undefined,
      landmark: formData.landmark || undefined,
      upvotes: 0,
      userId: state.user?.id || '1',
      location: { lat: 23.3441 + Math.random() * 0.01, lng: 85.3096 + Math.random() * 0.01 }
    };

    // Dispatch an action to save the draft
    dispatch({ type: 'SAVE_DRAFT', payload: draftIssue });

    // Add notification for saving draft
    dispatch({
      type: 'ADD_NOTIFICATION',
      payload: {
        id: Date.now().toString(),
        title: 'Report Saved as Draft',
        description: `Your report "${formData.title}" has been saved.`,
        date: new Date().toISOString(),
        type: 'info'
      }
    });

    // Optionally, navigate or clear the form
    navigate('/my-reports');
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] p-4">
        <h1 className="text-xl font-bold text-white">Report Issue</h1>
      </div>

      <form onSubmit={handleSubmit} className="p-4 space-y-6">
        {/* Photo Section */}
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">Add Photo *</label>

          {formData.image ? (
            <div className="relative">
              <img
                src={formData.image}
                alt="Issue"
                className="w-full h-48 object-cover rounded-xl"
              />
              <button
                type="button"
                onClick={() => setFormData(prev => ({ ...prev, image: null }))}
                className="absolute top-2 right-2 bg-red-500 text-white p-2 rounded-full hover:bg-red-600"
              >
                ×
              </button>
            </div>
          ) : cameraOpen ? (
            <div className="relative w-full h-64">
              <Webcam
                audio={false}
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                videoConstraints={{
                  facingMode: useFrontCamera ? 'user' : 'environment'
                }}
                className="w-full h-full object-cover rounded-xl"
              />
              <div className="absolute bottom-2 left-2 flex space-x-2">
                <button
                  type="button"
                  onClick={handleCapture}
                  className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white px-4 py-2 rounded-lg"
                >
                  Capture
                </button>
                <button
                  type="button"
                  onClick={() => setUseFrontCamera(prev => !prev)}
                  className="bg-gray-500 text-white px-4 py-2 rounded-lg flex items-center space-x-1"
                >
                  <RotateCw className="w-4 h-4" />
                  <span>Flip</span>
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setCameraOpen(true)}
              className="w-full h-48 border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center hover:border-green-400 transition-colors"
            >
              <Camera className="w-12 h-12 text-gray-400 mb-2" />
              <p className="text-gray-600">Open Camera</p>
            </button>
          )}
        </div>

        {/* Title */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Title *</label>
          <input
            type="text"
            value={formData.title}
            onChange={e => setFormData(prev => ({ ...prev, title: e.target.value }))}
            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500"
            placeholder="Brief description of the issue"
            required
          />
        </div>

        {/* Description & Audio */}
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">Description</label>
          <textarea
            value={formData.description}
            onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 min-h-[100px]"
            placeholder="Detailed description of the issue..."
          />

          {/* Audio Recorder */}
          <div className="bg-gray-50 rounded-xl p-4 space-y-3">
            <p className="text-sm font-medium text-gray-700">Or record audio (max 1 minute)</p>
            <div className="flex items-center justify-between">
              {!isRecording && !audioUrl && (
                <button
                  type="button"
                  onClick={startRecording}
                  className="flex items-center space-x-2 bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition-colors"
                >
                  <Mic className="w-4 h-4" />
                  <span>Start Recording</span>
                </button>
              )}
              {isRecording && (
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                    <span className="text-sm font-medium">Recording...</span>
                    <span className="text-sm text-gray-600">{formatTime(recordingTime)}</span>
                  </div>
                  <button
                    type="button"
                    onClick={stopRecording}
                    className="flex items-center space-x-1 bg-gray-600 text-white px-3 py-1 rounded-lg hover:bg-gray-700 transition-colors"
                  >
                    <Square className="w-4 h-4" />
                    <span>Stop</span>
                  </button>
                </div>
              )}
              {audioUrl && (
                <div className="flex items-center space-x-4 w-full">
                  <audio controls className="flex-1">
                    <source src={audioUrl} type="audio/wav" />
                  </audio>
                  <button
                    type="button"
                    onClick={clearRecording}
                    className="text-red-600 hover:text-red-700 text-sm"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Category */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Category *</label>
          <div className="relative">
            <select
              value={formData.category}
              onChange={e => setFormData(prev => ({ ...prev, category: e.target.value }))}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 appearance-none"
              required
            >
              <option value="roads">Roads & Transportation</option>
              <option value="sanitation">Sanitation</option>
              <option value="water">Water</option>
              <option value="lighting">Street Lighting</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          </div>
        </div>

        {/* Landmark */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Landmark (Optional)</label>
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={formData.landmark}
              onChange={e => setFormData(prev => ({ ...prev, landmark: e.target.value }))}
              className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500"
              placeholder="Near landmark or address"
            />
          </div>
        </div>

        <motion.button
          type="submit"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="w-full py-4 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
          disabled={!formData.title || !formData.image}
        >
          Submit Report
        </motion.button>

        <motion.button
          type="button"
          onClick={handleSaveDraft}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="w-full py-4 bg-gray-200 text-gray-800 font-semibold rounded-xl hover:bg-gray-300 transition-all duration-300 mt-2"
        >
          Save as Draft
        </motion.button>
      </form>

      <BottomNavigation />
    </div>
  );
};

export default ReportIssue;