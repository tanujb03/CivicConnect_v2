import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Camera, Mic, Square, MapPin, ChevronDown, RotateCw, Send, Save, AlertCircle } from 'lucide-react';
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

    dispatch({ type: 'ADD_ISSUE', payload: newIssue });

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

    setFormData({ title: '', description: '', category: 'roads', landmark: '', image: null });
    clearRecording();
    navigate('/my-reports');
  };

  const handleSaveDraft = () => {
    const draftIssue = {
      id: Date.now().toString(),
      title: formData.title,
      description: formData.description,
      category: formData.category as any,
      status: 'draft' as const,
      date: new Date().toISOString().split('T')[0],
      image: formData.image,
      audio: audioUrl || undefined,
      landmark: formData.landmark || undefined,
      upvotes: 0,
      userId: state.user?.id || '1',
      location: { lat: 23.3441 + Math.random() * 0.01, lng: 85.3096 + Math.random() * 0.01 }
    };

    dispatch({ type: 'SAVE_DRAFT', payload: draftIssue });

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

    navigate('/my-reports');
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec] pb-24">
      {/* Premium Header */}
      <div className="header-civic text-white px-5 pt-6 pb-5">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
            <Camera className="w-4 h-4 text-white/80" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight">Report Issue</h1>
            <p className="text-[11px] text-white/40 font-medium">Submit a civic problem report</p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="px-5 pt-5 space-y-5">
        {/* Photo Section */}
        <div className="space-y-2">
          <label className="block text-sm font-semibold text-gray-700">
            Add Photo <span className="text-red-400">*</span>
          </label>

          {formData.image ? (
            <div className="relative rounded-2xl overflow-hidden shadow-glass">
              <img
                src={formData.image}
                alt="Issue"
                className="w-full h-48 object-cover"
              />
              <button
                type="button"
                onClick={() => setFormData(prev => ({ ...prev, image: null }))}
                className="absolute top-3 right-3 w-8 h-8 bg-red-500/90 backdrop-blur-sm text-white rounded-xl flex items-center justify-center hover:bg-red-600 transition-colors shadow-lg"
              >
                ×
              </button>
            </div>
          ) : cameraOpen ? (
            <div className="relative w-full h-64 rounded-2xl overflow-hidden shadow-glass">
              <Webcam
                audio={false}
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                videoConstraints={{
                  facingMode: useFrontCamera ? 'user' : 'environment'
                }}
                className="w-full h-full object-cover"
              />
              <div className="absolute bottom-3 left-3 flex gap-2">
                <button
                  type="button"
                  onClick={handleCapture}
                  className="btn-civic px-4 py-2 text-sm rounded-xl"
                >
                  Capture
                </button>
                <button
                  type="button"
                  onClick={() => setUseFrontCamera(prev => !prev)}
                  className="bg-gray-800/80 backdrop-blur-sm text-white px-3 py-2 rounded-xl flex items-center gap-1.5 text-sm"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                  <span>Flip</span>
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setCameraOpen(true)}
              className="w-full h-44 border-2 border-dashed border-emerald-200 rounded-2xl flex flex-col items-center justify-center hover:border-emerald-400 hover:bg-emerald-50/30 transition-all duration-300 group"
            >
              <div className="w-14 h-14 rounded-2xl bg-emerald-50 flex items-center justify-center mb-3 group-hover:bg-emerald-100 transition-colors">
                <Camera className="w-7 h-7 text-emerald-500" />
              </div>
              <p className="text-gray-500 font-medium text-sm">Tap to open camera</p>
              <p className="text-xs text-gray-400 mt-0.5">Take a photo of the issue</p>
            </button>
          )}
        </div>

        {/* Title */}
        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-gray-700">
            Title <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={formData.title}
            onChange={e => setFormData(prev => ({ ...prev, title: e.target.value }))}
            className="input-civic"
            placeholder="Brief description of the issue"
            required
          />
        </div>

        {/* Description & Audio */}
        <div className="space-y-3">
          <label className="block text-sm font-semibold text-gray-700">Description</label>
          <textarea
            value={formData.description}
            onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
            className="input-civic min-h-[100px] resize-none"
            placeholder="Detailed description of the issue..."
          />

          {/* Audio Recorder */}
          <div className="glass-card p-4 space-y-3">
            <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
              <Mic className="w-3.5 h-3.5 text-gray-400" />
              Or record audio <span className="text-gray-400 font-normal">(max 1 min)</span>
            </p>
            <div className="flex items-center justify-between">
              {!isRecording && !audioUrl && (
                <button
                  type="button"
                  onClick={startRecording}
                  className="flex items-center gap-2 bg-red-500 text-white px-4 py-2.5 rounded-xl hover:bg-red-600 transition-colors text-sm font-semibold shadow-sm"
                >
                  <Mic className="w-4 h-4" />
                  <span>Start Recording</span>
                </button>
              )}
              {isRecording && (
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse"></div>
                    <span className="text-sm font-semibold text-gray-700">Recording...</span>
                    <span className="text-sm text-gray-500 font-mono">{formatTime(recordingTime)}</span>
                  </div>
                  <button
                    type="button"
                    onClick={stopRecording}
                    className="flex items-center gap-1.5 bg-gray-700 text-white px-3 py-2 rounded-xl hover:bg-gray-800 transition-colors text-sm font-medium"
                  >
                    <Square className="w-3.5 h-3.5" />
                    <span>Stop</span>
                  </button>
                </div>
              )}
              {audioUrl && (
                <div className="flex items-center gap-3 w-full">
                  <audio controls className="flex-1 h-10">
                    <source src={audioUrl} type="audio/wav" />
                  </audio>
                  <button
                    type="button"
                    onClick={clearRecording}
                    className="text-red-500 hover:text-red-600 text-xs font-semibold px-2 py-1 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Category */}
        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-gray-700">
            Category <span className="text-red-400">*</span>
          </label>
          <div className="relative">
            <select
              value={formData.category}
              onChange={e => setFormData(prev => ({ ...prev, category: e.target.value }))}
              className="input-civic appearance-none pr-10"
              required
            >
              <option value="roads">Roads & Transportation</option>
              <option value="sanitation">Sanitation</option>
              <option value="water">Water</option>
              <option value="lighting">Street Lighting</option>
            </select>
            <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Landmark */}
        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-gray-700">Landmark (Optional)</label>
          <div className="relative">
            <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={formData.landmark}
              onChange={e => setFormData(prev => ({ ...prev, landmark: e.target.value }))}
              className="input-civic pl-10"
              placeholder="Near landmark or address"
            />
          </div>
        </div>

        {/* Validation hint */}
        {(!formData.title || !formData.image) && (
          <div className="flex items-center gap-2 text-xs text-gray-400 bg-gray-50 rounded-xl px-4 py-2.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>Photo and title are required to submit</span>
          </div>
        )}

        {/* Submit */}
        <motion.button
          type="submit"
          whileTap={{ scale: 0.97 }}
          className="w-full py-4 text-white font-bold rounded-2xl text-[15px] transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          style={{
            background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)',
            boxShadow: formData.title && formData.image ? '0 8px 30px rgba(22, 163, 74, 0.3)' : 'none',
          }}
          disabled={!formData.title || !formData.image}
        >
          <Send className="w-4 h-4" />
          Submit Report
        </motion.button>

        {/* Save Draft */}
        <motion.button
          type="button"
          onClick={handleSaveDraft}
          whileTap={{ scale: 0.97 }}
          className="w-full py-3.5 bg-gray-100 text-gray-600 font-semibold rounded-2xl hover:bg-gray-200 transition-all duration-300 flex items-center justify-center gap-2 text-sm"
        >
          <Save className="w-4 h-4" />
          Save as Draft
        </motion.button>
      </form>

      <BottomNavigation />
    </div>
  );
};

export default ReportIssue;