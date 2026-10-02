import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { transitionMessages } from '../data/mockData';

interface TransitionScreenProps {
  onComplete: () => void;
}

const TransitionScreen: React.FC<TransitionScreenProps> = ({ onComplete }) => {
  const [currentMessage, setCurrentMessage] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentMessage((prev) => {
        if (prev < transitionMessages.length - 1) {
          return prev + 1;
        } else {
          setTimeout(onComplete, 1000);
          return prev;
        }
      });
    }, 1500);

    return () => clearInterval(timer);
  }, [onComplete]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 civic-mesh-bg flex items-center justify-center z-50"
    >
      {/* Decorative orbs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 4, repeat: Infinity }}
          className="absolute top-1/4 left-1/4 w-40 h-40 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.15) 0%, transparent 70%)' }}
        />
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.2, 0.4, 0.2] }}
          transition={{ duration: 5, repeat: Infinity, delay: 1 }}
          className="absolute bottom-1/3 right-1/4 w-56 h-56 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(108,199,122,0.1) 0%, transparent 70%)' }}
        />
      </div>

      {/* Progress dots */}
      <div className="absolute bottom-20 flex gap-2">
        {transitionMessages.map((_, i) => (
          <motion.div
            key={i}
            animate={{
              width: i === currentMessage ? 24 : 6,
              backgroundColor: i <= currentMessage ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.2)',
            }}
            transition={{ duration: 0.3 }}
            className="h-1.5 rounded-full"
          />
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={currentMessage}
          initial={{ y: 30, opacity: 0, scale: 0.95 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: -30, opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
          className="text-center text-white px-8 relative z-10"
        >
          <p className="text-2xl font-bold tracking-tight text-shadow-lg">
            {transitionMessages[currentMessage]}
          </p>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
};

export default TransitionScreen;