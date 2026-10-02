import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Eye, Camera, Mic, Map, Users, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import { DepartmentIcon } from './DepartmentIcon';

const slides = [
  {
    id: 1,
    title: 'Spot an Issue?',
    subtitle: 'See civic problems in your area? We can help you report them!',
    icon: Eye,
    iconBg: 'from-emerald-400 to-emerald-600',
    iconColor: 'text-white',
  },
  {
    id: 2,
    title: 'Click & Upload',
    subtitle: 'Capture the issue with your camera and select the problem category',
    icon: Camera,
    iconBg: 'from-blue-400 to-blue-600',
    iconColor: 'text-white',
  },
  {
    id: 3,
    title: 'Describe the Issue',
    subtitle: 'Describe the issue in text or record a voice note up to 1 minute',
    icon: Mic,
    iconBg: 'from-purple-400 to-purple-600',
    iconColor: 'text-white',
  },
  {
    id: 4,
    title: 'Track Progress',
    subtitle: 'Track issues on the map and filter by department or status',
    icon: Map,
    iconBg: 'from-amber-400 to-amber-600',
    iconColor: 'text-white',
  },
  {
    id: 5,
    title: 'Join Community',
    subtitle: 'Be part of the community, make your city better together',
    icon: Users,
    iconBg: 'from-rose-400 to-rose-600',
    iconColor: 'text-white',
  },
];

const Onboarding: React.FC = () => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [direction, setDirection] = useState(1);
  const navigate = useNavigate();

  const nextSlide = () => {
    if (currentSlide < slides.length - 1) {
      setDirection(1);
      setCurrentSlide(currentSlide + 1);
    } else {
      navigate('/login');
    }
  };

  const prevSlide = () => {
    if (currentSlide > 0) {
      setDirection(-1);
      setCurrentSlide(currentSlide - 1);
    }
  };

  const skipToLogin = () => {
    navigate('/login');
  };

  const slide = slides[currentSlide];
  const Icon = slide.icon;

  const variants = {
    enter: (dir: number) => ({ x: dir > 0 ? 200 : -200, opacity: 0, scale: 0.95 }),
    center: { x: 0, opacity: 1, scale: 1 },
    exit: (dir: number) => ({ x: dir > 0 ? -200 : 200, opacity: 0, scale: 0.95 }),
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec] flex flex-col relative overflow-hidden">
      {/* Background decorative orbs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full opacity-30"
             style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.1) 0%, transparent 70%)' }} />
        <div className="absolute -bottom-20 -left-20 w-48 h-48 rounded-full opacity-30"
             style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.08) 0%, transparent 70%)' }} />
      </div>

      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-4 relative z-10">
        <button
          onClick={prevSlide}
          className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 ${
            currentSlide === 0 ? 'invisible' : 'bg-white/80 backdrop-blur-sm border border-gray-200/50 hover:bg-gray-50 shadow-sm'
          }`}
          disabled={currentSlide === 0}
        >
          <ChevronLeft className="w-5 h-5 text-gray-600" />
        </button>
        
        {/* Progress dots */}
        <div className="flex gap-2">
          {slides.map((_, index) => (
            <motion.div
              key={index}
              animate={{
                width: index === currentSlide ? 24 : 8,
                backgroundColor: index === currentSlide ? '#16a34a' : '#d1d5db',
              }}
              transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
              className="h-2 rounded-full"
            />
          ))}
        </div>
        
        <button
          onClick={skipToLogin}
          className="text-sm text-gray-400 hover:text-emerald-600 font-medium px-3 py-1.5 rounded-lg hover:bg-emerald-50/50 transition-all duration-300"
        >
          Skip
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col justify-center items-center px-8 relative z-10">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={currentSlide}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
            className="text-center space-y-8 w-full max-w-sm"
          >
            {/* Icon */}
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.15, type: 'spring', stiffness: 200, damping: 20 }}
              className="flex justify-center"
            >
              <div className="relative">
                <div className={`w-32 h-32 rounded-3xl bg-gradient-to-br ${slide.iconBg} flex items-center justify-center shadow-xl`}
                     style={{ boxShadow: '0 20px 50px -10px rgba(0,0,0,0.15)' }}>
                  <Icon className={`w-14 h-14 ${slide.iconColor}`} />
                </div>
                {/* Glow effect */}
                <div className={`absolute inset-0 rounded-3xl bg-gradient-to-br ${slide.iconBg} opacity-20 blur-xl scale-110`} />
              </div>
            </motion.div>

            {/* Text */}
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.25 }}
              className="space-y-3"
            >
              <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight">
                {slide.title}
              </h2>
              <p className="text-gray-500 leading-relaxed text-[15px] max-w-xs mx-auto">
                {slide.subtitle}
              </p>
            </motion.div>

            {/* Extra content for specific slides */}
            {currentSlide === 1 && (
              <motion.div
                initial={{ y: 15, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.35 }}
                className="grid grid-cols-4 gap-3 pt-2"
              >
                {(['roads', 'sanitation', 'water', 'lighting'] as const).map((cat) => (
                  <div key={cat} className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-white/60 backdrop-blur-sm border border-gray-100/50">
                    <DepartmentIcon category={cat} size="md" />
                    <span className="text-[10px] text-gray-500 font-medium capitalize">{cat}</span>
                  </div>
                ))}
              </motion.div>
            )}

            {currentSlide === 3 && (
              <motion.div
                initial={{ y: 15, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.35 }}
                className="flex items-center justify-center gap-4"
              >
                {[
                  { label: 'Submitted', color: 'bg-red-400' },
                  { label: 'In Progress', color: 'bg-amber-400' },
                  { label: 'Resolved', color: 'bg-emerald-400' },
                ].map((status) => (
                  <div key={status.label} className="flex items-center gap-1.5">
                    <div className={`w-2.5 h-2.5 rounded-full ${status.color}`} />
                    <span className="text-xs text-gray-500 font-medium">{status.label}</span>
                  </div>
                ))}
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Bottom section */}
      <div className="px-6 pb-8 pt-4 relative z-10">
        <motion.button
          onClick={nextSlide}
          whileTap={{ scale: 0.97 }}
          className="w-full py-4 text-white font-bold rounded-2xl text-[15px] shadow-lg transition-all duration-300 hover:shadow-xl relative overflow-hidden"
          style={{
            background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)',
            boxShadow: '0 8px 30px rgba(22, 163, 74, 0.3)',
          }}
        >
          <span className="relative z-10 flex items-center justify-center gap-2">
            {currentSlide === slides.length - 1 ? (
              <>
                <Sparkles className="w-4 h-4" />
                Get Started
              </>
            ) : (
              <>
                Next
                <ChevronRight className="w-4 h-4" />
              </>
            )}
          </span>
        </motion.button>

        {/* Page indicator text */}
        <p className="text-center text-xs text-gray-400 mt-3 font-medium">
          {currentSlide + 1} of {slides.length}
        </p>
      </div>
    </div>
  );
};

export default Onboarding;