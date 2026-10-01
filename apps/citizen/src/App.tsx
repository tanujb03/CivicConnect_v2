import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { AppProvider } from './context/AppContext';
import Welcome from './components/Welcome';
import Onboarding from './components/Onboarding';
import Login from './components/Login';
import TransitionScreen from './components/TransitionScreen';
import Dashboard from './components/Dashboard';
import MyReports from './components/MyReports';
import ReportIssue from './components/ReportIssue';
import Community from './components/Community';
import Profile from './components/Profile';
import ExpandedMap from './components/ExpandedMap';
import IssueDetail from './components/IssueDetail';
import Notifications from './components/Notifications';

function App() {
  const [showTransition, setShowTransition] = useState(false);

  return (
    <AppProvider>
      <Router>
        <div className="min-h-screen bg-gray-50">
          <AnimatePresence mode="wait">
            {showTransition && (
              <TransitionScreen onComplete={() => setShowTransition(false)} />
            )}
          </AnimatePresence>
          
          <Routes>
            <Route path="/" element={<Welcome />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/login" element={<Login onLoginSuccess={() => setShowTransition(true)} />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/my-reports" element={<MyReports />} />
            <Route path="/report" element={<ReportIssue />} />
            <Route path="/community" element={<Community />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/map" element={<ExpandedMap />} />
            <Route path="/issue/:id" element={<IssueDetail />} />
            <Route path="/notifications" element={<Notifications />} />
          </Routes>
        </div>
      </Router>
    </AppProvider>
  );
}

export default App;