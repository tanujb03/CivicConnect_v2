import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
// import { Eye } from 'lucide-react'; // We will remove this if not used elsewhere

// Import your logo image
import logo from '../assets/logo.jpeg'; 

const Welcome: React.FC = () => {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="min-h-screen bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] flex flex-col items-center justify-between px-6 py-8 text-white relative overflow-hidden"
    >
      {/* Skip Button */}
      <div className="absolute top-8 right-6 z-10">
        <button
          onClick={() => navigate('/login')}
          className="text-white/80 hover:text-white transition-colors"
        >
          Skip
        </button>
      </div>

      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-20 left-10 w-32 h-32 border border-white/20 rounded-full"></div>
        <div className="absolute bottom-40 right-10 w-24 h-24 border border-white/20 rounded-full"></div>
        <div className="absolute top-1/2 left-1/4 w-16 h-16 border border-white/20 rounded-full"></div>
      </div>

      {/* Hero Section */}
      <div className="flex-1 flex flex-col items-center justify-center text-center space-y-8">
        {/* Logo */}
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="w-24 h-24 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm overflow-hidden" // Added overflow-hidden to ensure image respects rounded-full
        >
          <img 
            src={logo} 
            alt="CivicConnect Logo" 
            className="w-full h-full object-cover" // Ensure image covers the div
          />
        </motion.div>

        {/* App Title */}
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="space-y-2"
        >
          <h1 className="text-4xl font-bold">CivicConnect</h1>
          <p className="text-lg text-white/90">Make Your City Better</p>
        </motion.div>

        {/* Tagline */}
        <motion.p
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.7 }}
          className="text-white/80 max-w-xs text-center leading-relaxed"
        >
          Report civic issues, track progress, and be part of the community making positive changes
        </motion.p>
      </div>

      {/* Get Started Button */}
      <motion.div
        initial={{ y: 50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.9 }}
        className="w-full max-w-sm"
      >
        <button
          onClick={() => navigate('/onboarding')}
          className="w-full py-4 bg-white text-green-600 font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105"
        >
          Get Started
        </button>
      </motion.div>
    </motion.div>
  );
};

export default Welcome;