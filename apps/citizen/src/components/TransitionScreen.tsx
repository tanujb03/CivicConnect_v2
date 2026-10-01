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
      className="fixed inset-0 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] flex items-center justify-center z-50"
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={currentMessage}
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -30, opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center text-white px-6"
        >
          <p className="text-2xl font-semibold">
            {transitionMessages[currentMessage]}
          </p>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
};

export default TransitionScreen;