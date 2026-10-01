import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Flag, Phone, User } from 'lucide-react';
import { useApp } from '../context/AppContext';
import logo from '../assets/logo.jpeg';

interface LoginProps {
  onLoginSuccess: () => void;
}

const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const navigate = useNavigate();
  const { dispatch } = useApp();

  // ✅ Moved hook to top
  const [language, setLanguage] = useState<'en' | 'hi'>('en');
  const [step, setStep] = useState<'select' | 'form' | 'otp'>('select');
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    otp: ''
  });

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setStep('otp');
  };

  const handleOtpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Mock user creation
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

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="min-h-screen bg-white flex flex-col"
    >
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white p-4">
  <div className="flex items-center justify-between">
    <div className="flex items-center space-x-3">
      <div className="w-8 h-8 rounded-full overflow-hidden flex items-center justify-center">
        <img
          src={logo}
          alt="Jharkhand Government Logo"
          className="w-full h-full object-cover"
        />
      </div>
      <div>
        <p className="text-sm opacity-90">Gov. of Jharkhand</p>
        <p className="font-semibold">CivicConnect</p>
      </div>
    </div>
    {/* ✅ Fixed language dropdown */}
    <div className="flex items-center space-x-2">
      <Flag className="w-5 h-5" />
      <select
        className="bg-transparent text-white text-sm"
        value={language}
        onChange={(e) => setLanguage(e.target.value as 'en' | 'hi')}
      >
        <option value="en">English</option>
        <option value="hi">हिन्दी</option>
      </select>
    </div>
  </div>
</div>

      <div className="flex-1 p-6">
        {step === 'select' && (
          <motion.div
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className="space-y-6"
          >
            <div className="text-center space-y-4">
              <h2 className="text-2xl font-bold text-gray-800">
                {language === 'en'
                  ? 'Welcome to CivicConnect'
                  : 'सिविककनेक्ट में आपका स्वागत है'}
              </h2>
              <p className="text-gray-600">
                {language === 'en'
                  ? "Choose how you'd like to participate"
                  : 'कृपया लॉगिन का तरीका चुनें'}
              </p>
            </div>

            <div className="space-y-4">
              <button
                onClick={() => setStep('form')}
                className="w-full p-6 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] border-2 border-green-200 rounded-xl hover:border-green-300 transition-colors"
              >
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] rounded-full flex items-center justify-center">
                    <User className="w-6 h-6 text-green-600" />
                  </div>
                  <div className="text-left">
                    <h3 className="font-semibold text-white">
                      {language === 'en' ? 'Login as Citizen' : 'नागरिक के रूप में लॉगिन करें'}
                    </h3>
                    <p className="text-sm text-white/90">
                      {language === 'en'
                        ? 'Report issues and track progress'
                        : 'समस्याएं रिपोर्ट करें और प्रगति देखें'}
                    </p>
                  </div>
                </div>
              </button>
            </div>
          </motion.div>
        )}

        {step === 'form' && (
          <motion.div
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className="space-y-6"
          >
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-800">
                {language === 'en' ? 'Citizen Registration' : 'नागरिक पंजीकरण'}
              </h2>
            </div>

            <form onSubmit={handleFormSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {language === 'en' ? 'Full Name' : 'पूरा नाम'}
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  placeholder={language === 'en' ? 'Enter your full name' : 'अपना पूरा नाम दर्ज करें'}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {language === 'en'
                    ? 'Aadhaar-verified Phone Number'
                    : 'आधार-सत्यापित फोन नंबर'}
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500"
                    placeholder="+91 XXXXX XXXXX"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
              >
                {language === 'en' ? 'Send OTP' : 'ओटीपी भेजें'}
              </button>
            </form>
          </motion.div>
        )}

        {step === 'otp' && (
          <motion.div
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className="space-y-6"
          >
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-800">
                {language === 'en' ? 'Verify OTP' : 'ओटीपी सत्यापित करें'}
              </h2>
              <p className="text-gray-600 mt-2">
                {language === 'en'
                  ? `Enter the OTP sent to ${formData.phone}`
                  : ` ${formData.phone} पर भेजा गया ओटीपी दर्ज करें`}
              </p>
            </div>

            <form onSubmit={handleOtpSubmit} className="space-y-4">
              <div>
                <input
                  type="text"
                  value={formData.otp}
                  onChange={(e) => setFormData({ ...formData, otp: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 text-center text-2xl tracking-widest"
                  placeholder="000000"
                  maxLength={6}
                  required
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
              >
                {language === 'en' ? 'Verify & Continue' : 'सत्यापित करें और जारी रखें'}
              </button>

              <button
                type="button"
                className="w-full text-gradient-to-b from-[#1A531A] to-[#7CAE0C] hover:text-green-700"
              >
                {language === 'en' ? 'Resend OTP' : 'ओटीपी पुनः भेजें'}
              </button>
            </form>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

export default Login;
