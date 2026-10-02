import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Flag, Phone, User, ArrowRight, Shield, Sparkles } from 'lucide-react';
import { useApp } from '../context/AppContext';
import logo from '../assets/logo.jpeg';

interface LoginProps {
  onLoginSuccess: () => void;
}

const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const navigate = useNavigate();
  const { dispatch } = useApp();

  const [language, setLanguage] = useState<'en' | 'hi'>('en');
  const [step, setStep] = useState<'select' | 'form' | 'otp'>('select');
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    otp: '',
  });

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setStep('otp');
  };

  const handleOtpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const user = {
      id: '1',
      name: formData.name,
      phone: formData.phone,
      avatar:
        'https://images.pexels.com/photos/771742/pexels-photo-771742.jpeg?auto=compress&cs=tinysrgb&w=100&h=100&fit=crop',
      address: 'Ranchi, Jharkhand',
      ward: 'Ward 15',
    };
    dispatch({ type: 'SET_USER', payload: user });
    onLoginSuccess();
    navigate('/dashboard');
  };

  const pageVariants = {
    enter: { x: 80, opacity: 0 },
    center: { x: 0, opacity: 1 },
    exit: { x: -80, opacity: 0 },
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec] flex flex-col relative overflow-hidden"
    >
      {/* Background decorative elements */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-20 -right-20 w-80 h-80 rounded-full opacity-30"
             style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.12) 0%, transparent 70%)' }} />
        <div className="absolute -bottom-20 -left-20 w-60 h-60 rounded-full opacity-30"
             style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.1) 0%, transparent 70%)' }} />
      </div>

      {/* Premium Header */}
      <div className="header-civic text-white px-5 py-4 relative z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl overflow-hidden border border-white/20 shadow-lg bg-white/10 p-0.5">
              <img src={logo} alt="Logo" className="w-full h-full object-cover rounded-lg" />
            </div>
            <div>
              <p className="text-[11px] text-white/60 font-medium tracking-wider uppercase">Gov. of Jharkhand</p>
              <p className="font-bold text-[15px] tracking-tight">CivicConnect</p>
            </div>
          </div>
          <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-xl px-3 py-1.5 border border-white/10">
            <Flag className="w-3.5 h-3.5 text-white/70" />
            <select
              className="bg-transparent text-white text-xs font-medium focus:outline-none cursor-pointer"
              value={language}
              onChange={(e) => setLanguage(e.target.value as 'en' | 'hi')}
            >
              <option value="en" className="text-gray-800">English</option>
              <option value="hi" className="text-gray-800">हिन्दी</option>
            </select>
          </div>
        </div>
      </div>

      <div className="flex-1 px-6 py-8 relative z-10">
        <AnimatePresence mode="wait">
          {step === 'select' && (
            <motion.div
              key="select"
              variants={pageVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
              className="space-y-8"
            >
              <div className="text-center space-y-3">
                <motion.div
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.1 }}
                >
                  <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight">
                    {language === 'en' ? 'Welcome Back' : 'स्वागत है'}
                  </h2>
                  <p className="text-gray-500 mt-2 text-[15px]">
                    {language === 'en' ? "Choose how you'd like to participate" : 'कृपया लॉगिन का तरीका चुनें'}
                  </p>
                </motion.div>
              </div>

              <motion.div
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="space-y-4"
              >
                <button
                  onClick={() => setStep('form')}
                  className="group w-full p-5 glass-card border-emerald-100/60 hover:border-emerald-200 hover:shadow-civic transition-all duration-400 text-left"
                >
                  <div className="flex items-center space-x-4">
                    <div className="w-14 h-14 rounded-2xl flex items-center justify-center shrink-0"
                         style={{ background: 'linear-gradient(145deg, #1a7a2e, #27a94a)' }}>
                      <User className="w-7 h-7 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-gray-900 text-[16px]">
                        {language === 'en' ? 'Login as Citizen' : 'नागरिक के रूप में लॉगिन'}
                      </h3>
                      <p className="text-sm text-gray-500 mt-0.5">
                        {language === 'en' ? 'Report issues and track progress' : 'समस्याएं रिपोर्ट करें'}
                      </p>
                    </div>
                    <ArrowRight className="w-5 h-5 text-gray-300 group-hover:text-emerald-500 group-hover:translate-x-1 transition-all duration-300" />
                  </div>
                </button>
              </motion.div>

              {/* Trust badges */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="flex items-center justify-center gap-6 pt-4"
              >
                <div className="flex items-center gap-1.5 text-gray-400">
                  <Shield className="w-3.5 h-3.5" />
                  <span className="text-xs font-medium">Secure Login</span>
                </div>
                <div className="w-px h-4 bg-gray-200" />
                <div className="flex items-center gap-1.5 text-gray-400">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span className="text-xs font-medium">Aadhaar Verified</span>
                </div>
              </motion.div>
            </motion.div>
          )}

          {step === 'form' && (
            <motion.div
              key="form"
              variants={pageVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
              className="space-y-6"
            >
              <div className="text-center">
                <h2 className="text-2xl font-extrabold text-gray-900 tracking-tight">
                  {language === 'en' ? 'Citizen Registration' : 'नागरिक पंजीकरण'}
                </h2>
                <p className="text-gray-500 text-sm mt-1">Enter your details to get started</p>
              </div>

              <form onSubmit={handleFormSubmit} className="space-y-5">
                <div className="space-y-1.5">
                  <label className="block text-sm font-semibold text-gray-700">
                    {language === 'en' ? 'Full Name' : 'पूरा नाम'}
                  </label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="input-civic pl-12"
                      placeholder={language === 'en' ? 'Enter your full name' : 'अपना पूरा नाम दर्ज करें'}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-semibold text-gray-700">
                    {language === 'en' ? 'Phone Number' : 'फोन नंबर'}
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-gray-400" />
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="input-civic pl-12"
                      placeholder="+91 XXXXX XXXXX"
                      required
                    />
                  </div>
                </div>

                <button type="submit" className="btn-civic w-full py-4 text-[15px] rounded-2xl">
                  <span className="flex items-center justify-center gap-2">
                    {language === 'en' ? 'Send OTP' : 'ओटीपी भेजें'}
                    <ArrowRight className="w-4 h-4" />
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setStep('select')}
                  className="w-full text-center text-sm text-gray-400 hover:text-gray-600 font-medium transition-colors"
                >
                  ← Back
                </button>
              </form>
            </motion.div>
          )}

          {step === 'otp' && (
            <motion.div
              key="otp"
              variants={pageVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
              className="space-y-6"
            >
              <div className="text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center"
                     style={{ background: 'linear-gradient(145deg, #e8f8ec, #d0f0d5)' }}>
                  <Shield className="w-8 h-8 text-emerald-600" />
                </div>
                <h2 className="text-2xl font-extrabold text-gray-900 tracking-tight">
                  {language === 'en' ? 'Verify OTP' : 'ओटीपी सत्यापित करें'}
                </h2>
                <p className="text-gray-500 text-sm mt-2">
                  {language === 'en'
                    ? `Enter the OTP sent to ${formData.phone}`
                    : `${formData.phone} पर भेजा गया ओटीपी दर्ज करें`}
                </p>
              </div>

              <form onSubmit={handleOtpSubmit} className="space-y-5">
                <div>
                  <input
                    type="text"
                    value={formData.otp}
                    onChange={(e) => setFormData({ ...formData, otp: e.target.value })}
                    className="input-civic text-center text-3xl tracking-[0.4em] font-bold"
                    placeholder="• • • • • •"
                    maxLength={6}
                    required
                  />
                </div>

                <button type="submit" className="btn-civic w-full py-4 text-[15px] rounded-2xl">
                  <span className="flex items-center justify-center gap-2">
                    {language === 'en' ? 'Verify & Continue' : 'सत्यापित करें'}
                    <ArrowRight className="w-4 h-4" />
                  </span>
                </button>

                <button
                  type="button"
                  className="w-full text-center text-sm text-emerald-600 hover:text-emerald-700 font-semibold transition-colors"
                >
                  {language === 'en' ? 'Resend OTP' : 'ओटीपी पुनः भेजें'}
                </button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

export default Login;
