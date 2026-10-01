import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Eye, Camera, Mic, Map, Users, ChevronLeft, ChevronRight } from 'lucide-react';
import { DepartmentIcon } from './DepartmentIcon';

const slides = [
  {
    id: 1,
    title: 'Spot an Issue?',
    content: (
      <div className="flex flex-col items-center space-y-6">
        <div className="w-32 h-32 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] rounded-full flex items-center justify-center">
          <Eye className="w-16 h-16 text-green-600" />
        </div>
        <p className="text-gray-600 text-center leading-relaxed">
          See civic problems in your area? We can help you report them!
        </p>
      </div>
    )
  },
  {
    id: 2,
    title: 'Click & Upload',
    content: (
      <div className="flex flex-col space-y-8">
        {/* Upper portion */}
        <div className="flex flex-col items-center space-y-4">
          <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center">
            <Camera className="w-12 h-12 text-blue-600" />
          </div>
          <p className="text-gray-600 text-center">Tap to capture the issue</p>
        </div>
        
        {/* Lower portion */}
        <div className="space-y-4">
          <p className="text-gray-600 text-center">Select the problem category</p>
          <div className="grid grid-cols-4 gap-4">
            <div className="flex flex-col items-center space-y-2">
              <DepartmentIcon category="roads" size="md" />
              <span className="text-xs text-gray-500">Roads</span>
            </div>
            <div className="flex flex-col items-center space-y-2">
              <DepartmentIcon category="sanitation" size="md" />
              <span className="text-xs text-gray-500">Sanitation</span>
            </div>
            <div className="flex flex-col items-center space-y-2">
              <DepartmentIcon category="water" size="md" />
              <span className="text-xs text-gray-500">Water</span>
            </div>
            <div className="flex flex-col items-center space-y-2">
              <DepartmentIcon category="lighting" size="md" />
              <span className="text-xs text-gray-500">Lighting</span>
            </div>
          </div>
        </div>
      </div>
    )
  },
  {
    id: 3,
    title: 'Describe the Issue',
    content: (
      <div className="flex flex-col items-center space-y-8">
        <div className="flex items-center space-x-8">
          <div className="w-24 h-24 bg-purple-100 rounded-full flex items-center justify-center">
            <div className="w-12 h-8 bg-purple-600 rounded"></div>
          </div>
          <div className="w-24 h-24 bg-red-100 rounded-full flex items-center justify-center">
            <Mic className="w-12 h-12 text-red-600" />
          </div>
        </div>
        <p className="text-gray-600 text-center leading-relaxed">
          Describe the issue in text or record a voice note up to 1 minute
        </p>
      </div>
    )
  },
  {
    id: 4,
    title: 'Track Progress',
    content: (
      <div className="flex flex-col space-y-6">
        <div className="bg-green-50 rounded-xl p-4 h-40 relative overflow-hidden">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-3 h-3 bg-red-500 rounded-full absolute top-8 left-8"></div>
            <div className="w-3 h-3 bg-yellow-500 rounded-full absolute top-12 right-12"></div>
            <div className="w-3 h-3 bg-green-500 rounded-full absolute bottom-8 left-12"></div>
            <div className="w-3 h-3 bg-red-500 rounded-full absolute bottom-12 right-8"></div>
          </div>
        </div>
        
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-red-500 rounded-full"></div>
              <span>Submitted</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
              <span>In Progress</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <span>Resolved</span>
            </div>
          </div>
          
          <div className="flex justify-between text-xs text-gray-500">
            <span>All</span>
            <span>Roads</span>
            <span>Sanitation</span>
            <span>Water</span>
            <span>Lighting</span>
          </div>
        </div>
        
        <p className="text-gray-600 text-center text-sm leading-relaxed">
          Track issues on the map and filter by department or status
        </p>
      </div>
    )
  },
  {
    id: 5,
    title: 'Join Community',
    content: (
      <div className="flex flex-col items-center space-y-6">
        <div className="w-32 h-32 bg-orange-100 rounded-full flex items-center justify-center">
          <Users className="w-16 h-16 text-orange-600" />
        </div>
        <p className="text-gray-600 text-center leading-relaxed">
          Be part of the community, make your city better together
        </p>
      </div>
    )
  }
];

const Onboarding: React.FC = () => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const navigate = useNavigate();

  const nextSlide = () => {
    if (currentSlide < slides.length - 1) {
      setCurrentSlide(currentSlide + 1);
    } else {
      navigate('/login');
    }
  };

  const prevSlide = () => {
    if (currentSlide > 0) {
      setCurrentSlide(currentSlide - 1);
    }
  };

  const skipToLogin = () => {
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Top taskbar */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] shadow-sm">
        <button
          onClick={prevSlide}
          className={`p-2 rounded-full ${
            currentSlide === 0 ? 'invisible' : 'hover:bg-gray-100'
          }`}
          disabled={currentSlide === 0}
        >
          <ChevronLeft className="w-5 h-5 text-gray-600" />
        </button>
        
        <div className="flex space-x-2">
          {slides.map((_, index) => (
            <div
              key={index}
              className={`w-2 h-2 rounded-full ${
                index === currentSlide ? 'bg-gradient-to-b from-[#1A531A] to-[#7CAE0C]' : 'bg-gray-300'
              }`}
            />
          ))}
        </div>
        
        <button
          onClick={skipToLogin}
          className="text-white hover:text-gray-800"
        >
          Skip
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col justify-center px-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentSlide}
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -300, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="text-center space-y-8"
          >
            <h2 className="text-2xl font-bold text-gray-800">
              {slides[currentSlide].title}
            </h2>
            <div className="min-h-[300px] flex items-center justify-center">
              {slides[currentSlide].content}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Next button */}
      <div className="p-6">
        <button
          onClick={nextSlide}
          className="w-full py-4 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
        >
          {currentSlide === slides.length - 1 ? 'Get Started' : 'Next'}
        </button>
      </div>
    </div>
  );
};

export default Onboarding;