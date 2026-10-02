import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import logo from '../assets/logo.jpeg';

const Welcome: React.FC = () => {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="min-h-screen civic-mesh-bg flex flex-col items-center justify-between px-6 py-10 text-white relative overflow-hidden"
    >
      {/* Animated Background Orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{ y: [0, -20, 0], x: [0, 10, 0], scale: [1, 1.1, 1] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-16 left-8 w-40 h-40 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(108,199,122,0.15) 0%, transparent 70%)' }}
        />
        <motion.div
          animate={{ y: [0, 15, 0], x: [0, -15, 0], scale: [1, 1.15, 1] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
          className="absolute bottom-32 right-6 w-56 h-56 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.12) 0%, transparent 70%)' }}
        />
        <motion.div
          animate={{ y: [0, -12, 0], x: [0, 8, 0] }}
          transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
          className="absolute top-1/2 left-1/3 w-28 h-28 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)' }}
        />

        {/* Subtle grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      {/* Skip Button */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2 }}
        className="absolute top-8 right-6 z-10"
      >
        <button
          onClick={() => navigate('/login')}
          className="text-white/60 hover:text-white text-sm font-medium px-4 py-2 rounded-full bg-white/5 hover:bg-white/10 backdrop-blur-sm border border-white/10 transition-all duration-300"
        >
          Skip →
        </button>
      </motion.div>

      {/* Hero Section */}
      <div className="flex-1 flex flex-col items-center justify-center text-center space-y-8 relative z-10">
        {/* Logo with glow */}
        <motion.div
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.3, type: 'spring', stiffness: 200, damping: 20 }}
          className="relative"
        >
          <div className="absolute inset-0 rounded-full blur-2xl opacity-40"
               style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.5) 0%, transparent 70%)', transform: 'scale(1.5)' }} />
          <div className="w-28 h-28 rounded-3xl overflow-hidden border-2 border-white/20 shadow-2xl relative backdrop-blur-sm bg-white/10 p-1">
            <img
              src={logo}
              alt="CivicConnect Logo"
              className="w-full h-full object-cover rounded-2xl"
            />
          </div>
        </motion.div>

        {/* App Title */}
        <motion.div
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.7 }}
          className="space-y-3"
        >
          <h1 className="text-5xl font-extrabold tracking-tight text-shadow-lg">
            CivicConnect
          </h1>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: 80 }}
            transition={{ delay: 0.9, duration: 0.5 }}
            className="h-1 bg-gradient-to-r from-white/60 to-white/10 rounded-full mx-auto"
          />
          <p className="text-xl font-medium text-white/85 text-shadow-sm">
            Make Your City Better
          </p>
        </motion.div>

        {/* Tagline */}
        <motion.p
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.7 }}
          className="text-white/65 max-w-xs text-center leading-relaxed text-[15px]"
        >
          Report civic issues, track progress, and be part of the community making positive changes
        </motion.p>

        {/* Feature pills */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.9 }}
          className="flex flex-wrap justify-center gap-2"
        >
          {['📍 Report Issues', '📊 Track Progress', '🤝 Community'].map((item, i) => (
            <motion.span
              key={item}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 1.0 + i * 0.1 }}
              className="px-4 py-1.5 rounded-full bg-white/10 backdrop-blur-sm border border-white/15 text-white/80 text-xs font-medium"
            >
              {item}
            </motion.span>
          ))}
        </motion.div>
      </div>

      {/* Get Started Button */}
      <motion.div
        initial={{ y: 60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 1.1, type: 'spring', stiffness: 150, damping: 20 }}
        className="w-full max-w-sm relative z-10"
      >
        <button
          onClick={() => navigate('/onboarding')}
          className="group w-full py-4 bg-white text-emerald-700 font-bold rounded-2xl shadow-premium relative overflow-hidden transition-all duration-500 hover:shadow-civic-lg hover:scale-[1.02] active:scale-[0.98]"
        >
          <span className="relative z-10 flex items-center justify-center gap-2 text-[16px]">
            Get Started
            <motion.span
              animate={{ x: [0, 4, 0] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              →
            </motion.span>
          </span>
          <div className="absolute inset-0 bg-gradient-to-r from-emerald-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </button>

        <p className="text-center text-white/40 text-xs mt-4 font-medium tracking-wide">
          Government of Jharkhand • Digital India
        </p>
      </motion.div>
    </motion.div>
  );
};

export default Welcome;