import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Bell, Camera, MapPin, TrendingUp, CheckCircle, Clock, ArrowLeft, ChevronRight, Newspaper } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import BottomNavigation from './BottomNavigation';
import logo from '../assets/logo.jpeg';

// Importing the Leaflet components from react-leaflet
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import { DepartmentIcon } from './DepartmentIcon';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.4, 0, 0.2, 1] } },
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useApp();
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);

  const departments = ['all', 'roads', 'sanitation', 'water', 'lighting'];

  const issues = state?.issues || [];
  const filteredIssues =
    selectedDepartment === 'all'
      ? issues
      : issues.filter((issue) => issue.category === selectedDepartment);

  const getMarkerIcon = (status: string) => {
    const redSVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#B91C1C" width="30px" height="42px"><path d="M12 0C7.31 0 3.5 3.81 3.5 8.5c0 5.25 8.5 15.5 8.5 15.5s8.5-10.25 8.5-15.5C20.5 3.81 16.69 0 12 0zm0 12.5a4 4 0 110-8 4 4 0 010 8z"/></svg>`;
    const yellowSVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#D97706" width="30px" height="42px"><path d="M12 0C7.31 0 3.5 3.81 3.5 8.5c0 5.25 8.5 15.5 8.5 15.5s8.5-10.25 8.5-15.5C20.5 3.81 16.69 0 12 0zm0 12.5a4 4 0 110-8 4 4 0 010 8z"/></svg>`;
    const greenSVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#15803D" width="30px" height="42px"><path d="M12 0C7.31 0 3.5 3.81 3.5 8.5c0 5.25 8.5 15.5 8.5 15.5s8.5-10.25 8.5-15.5C20.5 3.81 16.69 0 12 0zm0 12.5a4 4 0 110-8 4 4 0 010 8z"/></svg>`;

    let iconUrl;
    switch (status) {
      case 'submitted': iconUrl = 'data:image/svg+xml;base64,' + btoa(redSVG); break;
      case 'in-progress': iconUrl = 'data:image/svg+xml;base64,' + btoa(yellowSVG); break;
      case 'resolved': iconUrl = 'data:image/svg+xml;base64,' + btoa(greenSVG); break;
      default: iconUrl = 'data:image/svg+xml;base64,' + btoa(redSVG);
    }
    return iconUrl;
  };

  // Mock News
  const mockNews = [
    { id: 1, title: 'City Council Approves New Park Project', description: 'The council has approved a new park project aiming to increase green spaces for residents.', image: 'https://thatssotampa.com/wp-content/uploads/2022/10/BonnetSprings.jpg' },
    { id: 2, title: 'Community Clean-Up Event Scheduled', description: 'Join us for a community clean-up this Saturday at 9 AM. Volunteers are welcome!', image: 'https://tse4.mm.bing.net/th/id/OIP.xHj38LN-gpeIhWzFX7AwKAHaE8?pid=ImgDet&w=194&h=129&c=7&dpr=1.7&o=7&rm=3' },
    { id: 3, title: 'New Traffic Regulations Implemented', description: 'New traffic regulations are now in effect to improve traffic flow and safety.', image: 'https://images.pexels.com/photos/3972755/pexels-photo-3972755.jpeg?auto=compress&cs=tinysrgb&w=600' },
    { id: 4, title: 'Public Library Expansion Underway', description: 'Construction has begun on the new wing of the central library, expected to open next year.', image: 'https://cdn.fodors.com/wp-content/uploads/2017/09/Public-Libraries-Free-Library-of-Philadelphia-2.jpg' },
    { id: 5, title: 'Annual Water Quality Report Released', description: 'The city has released its annual water quality report, confirming that drinking water is safe.', image: 'https://tse2.mm.bing.net/th/id/OIP.PwpMvv8KnOTBPOOzsA37fwAAAA?rs=1&pid=ImgDetMain&o=7&rm=3' },
    { id: 6, title: 'Road Safety Campaign Launched', description: 'A new campaign aims to increase awareness about pedestrian and cyclist safety.', image: 'https://th.bing.com/th/id/R.3af6df04e9a2c2fe7ddeb25041d66130?rik=BduDFj%2b%2fGhVlVQ&riu=http%3a%2f%2fblog.trucksuvidha.com%2fwp-content%2fuploads%2f2019%2f02%2fsafety-road-1024x681.jpg&ehk=YJV%2bfDpx4ucrNjnSVMPqWTY%2fE7ifQH%2fUbzgigHCimqI%3d&risl=&pid=ImgRaw&r=0' },
  ];

  const mockStats = {
    totalIssues: issues.length,
    resolvedIssues: issues.filter((i) => i.status === 'resolved').length,
    avgResponseTime: '2d 5h',
  };

  const statCards = [
    { label: 'Total Issues', value: mockStats.totalIssues, icon: TrendingUp, color: 'from-blue-500 to-blue-600', bgLight: 'bg-blue-50' },
    { label: 'Resolved', value: mockStats.resolvedIssues, icon: CheckCircle, color: 'from-emerald-500 to-emerald-600', bgLight: 'bg-emerald-50' },
    { label: 'Avg Response', value: mockStats.avgResponseTime, icon: Clock, color: 'from-amber-500 to-amber-600', bgLight: 'bg-amber-50' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f0faf2] via-white to-[#e8f8ec] pb-28 relative">
      {!isMapFullscreen && (
        <>
          {/* ─── Premium Header ──────────────────────────────────── */}
          <div className="header-civic text-white px-5 pt-5 pb-6 relative">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl overflow-hidden border border-white/20 shadow-lg bg-white/10 p-0.5">
                  <img src={logo} alt="Logo" className="w-full h-full object-cover rounded-lg" />
                </div>
                <div>
                  <p className="text-[11px] text-white/50 font-medium tracking-wider uppercase">CivicConnect</p>
                  <p className="font-bold text-[16px] tracking-tight">Citizen Dashboard</p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <div className="flex items-center gap-1.5 bg-white/10 backdrop-blur-sm rounded-lg px-2.5 py-1.5 border border-white/10">
                  <MapPin className="w-3 h-3 text-white/70" />
                  <span className="text-xs text-white/80 font-medium">Ranchi</span>
                </div>
                <button
                  onClick={() => navigate('/notifications')}
                  className="relative p-2.5 hover:bg-white/10 rounded-xl transition-all duration-300"
                >
                  <Bell className="w-5 h-5" />
                  <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-emerald-800 animate-pulse" />
                </button>
                <div className="w-9 h-9 rounded-xl overflow-hidden border-2 border-white/20 shadow-lg">
                  <img
                    src={state.user?.avatar || 'https://images.pexels.com/photos/771742/pexels-photo-771742.jpeg?auto=compress&cs=tinysrgb&w=100&h=100&fit=crop'}
                    alt="Profile"
                    className="w-full h-full object-cover"
                  />
                </div>
              </div>
            </div>

            {/* ─── Stats Cards in Header ──────────────────────────── */}
            <motion.div
              variants={stagger}
              initial="hidden"
              animate="show"
              className="grid grid-cols-3 gap-3"
            >
              {statCards.map((s, i) => {
                const Icon = s.icon;
                return (
                  <motion.div
                    key={i}
                    variants={fadeUp}
                    className="bg-white/10 backdrop-blur-sm rounded-2xl p-3.5 text-center border border-white/10 hover:bg-white/15 transition-all duration-300 cursor-default group"
                  >
                    <div className="flex items-center justify-center mb-1.5">
                      <Icon className="w-4 h-4 text-white/70 group-hover:text-white transition-colors" />
                    </div>
                    <div className="text-xl font-extrabold tracking-tight">{s.value}</div>
                    <div className="text-[10px] text-white/60 font-medium mt-0.5 uppercase tracking-wider">{s.label}</div>
                  </motion.div>
                );
              })}
            </motion.div>
          </div>
        </>
      )}

      <motion.div
        variants={stagger}
        initial="hidden"
        animate="show"
        className="px-5 pt-6 space-y-6"
      >
        {/* ─── Map Section ──────────────────────────────────────── */}
        {!isMapFullscreen && (
          <motion.div variants={fadeUp} className="glass-card overflow-hidden">
            <div className="p-4 pb-3">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-bold text-gray-900 text-[15px]">Issues Near You</h3>
                <button
                  onClick={() => setIsMapFullscreen(true)}
                  className="text-xs text-emerald-600 font-semibold hover:text-emerald-700 flex items-center gap-0.5 transition-colors"
                >
                  Expand <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Department Filter Pills */}
              <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide -mx-1 px-1">
                {departments.map((dept) => (
                  <button
                    key={dept}
                    onClick={() => setSelectedDepartment(dept)}
                    className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full whitespace-nowrap text-xs font-semibold transition-all duration-300 ${
                      selectedDepartment === dept
                        ? 'bg-emerald-600 text-white shadow-civic'
                        : 'bg-gray-100/80 text-gray-600 hover:bg-gray-200/80'
                    }`}
                  >
                    {dept !== 'all' && <DepartmentIcon category={dept as any} size="sm" />}
                    <span className="capitalize">{dept === 'all' ? 'All Issues' : dept}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="h-56 w-full relative z-0 cursor-pointer" onClick={() => setIsMapFullscreen(true)}>
              <MapContainer
                center={[23.3441, 85.3096]}
                zoom={13}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {filteredIssues.map((issue, idx) => (
                  <Marker
                    key={issue.id || idx}
                    position={[issue.location.lat, issue.location.lng]}
                    eventHandlers={{ click: () => navigate(`/issue/${issue.id}`) }}
                    icon={new L.Icon({
                      iconUrl: getMarkerIcon(issue.status),
                      iconSize: [30, 42],
                      iconAnchor: [15, 42],
                      shadowUrl: markerShadow,
                    })}
                  >
                    <Popup><b>{issue.title}</b><br />Status: {issue.status}</Popup>
                  </Marker>
                ))}
              </MapContainer>
            </div>

            <div className="px-4 py-3 bg-gradient-to-r from-emerald-50/50 to-transparent border-t border-emerald-100/30">
              <p className="text-xs text-gray-500 font-medium">
                📍 Showing <span className="text-emerald-700 font-bold">{filteredIssues.length}</span> issues • Tap markers for details
              </p>
            </div>
          </motion.div>
        )}

        {/* ─── Report Issue CTA ─────────────────────────────────── */}
        {!isMapFullscreen && (
          <motion.div variants={fadeUp}>
            <button
              onClick={() => navigate('/report')}
              className="group w-full glass-card p-5 hover:shadow-civic transition-all duration-400 hover:border-emerald-200 text-left"
            >
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 relative"
                     style={{ background: 'linear-gradient(145deg, #1a7a2e, #27a94a)' }}>
                  <Camera className="w-7 h-7 text-white" />
                  <span className="absolute inset-0 rounded-2xl animate-pulse-glow" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-gray-900 text-[15px]">Report an Issue</h3>
                  <p className="text-xs text-gray-500 mt-0.5">Take a photo and report civic problems instantly</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-emerald-500 group-hover:translate-x-1 transition-all duration-300" />
              </div>
            </button>
          </motion.div>
        )}

        {/* ─── Civic News Carousel ──────────────────────────────── */}
        {!isMapFullscreen && (
          <motion.div variants={fadeUp} className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <Newspaper className="w-4 h-4 text-emerald-600" />
                <h3 className="font-bold text-gray-900 text-[15px]">Civic News</h3>
              </div>
              <span className="text-xs text-emerald-600 font-semibold">View All →</span>
            </div>

            <div className="flex gap-4 overflow-x-auto pb-3 -mx-5 px-5 scrollbar-hide snap-x snap-mandatory">
              {mockNews.map((news, i) => (
                <motion.div
                  key={news.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.1 + i * 0.05 }}
                  className="snap-start flex-shrink-0 w-[260px] glass-card overflow-hidden group cursor-pointer"
                >
                  <div className="h-32 overflow-hidden relative">
                    <img
                      src={news.image}
                      alt={news.title}
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent" />
                  </div>
                  <div className="p-3.5">
                    <h4 className="font-bold text-[13px] text-gray-900 leading-tight line-clamp-2">{news.title}</h4>
                    <p className="text-[11px] text-gray-500 mt-1.5 line-clamp-2 leading-relaxed">{news.description}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </motion.div>

      {/* ─── Fullscreen Map Modal ──────────────────────────────── */}
      {isMapFullscreen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 z-50 bg-gray-900 flex flex-col"
        >
          <div className="flex items-center p-4 bg-gray-900/90 backdrop-blur-lg border-b border-white/10">
            <button
              onClick={() => setIsMapFullscreen(false)}
              className="text-white p-2 rounded-xl hover:bg-white/10 transition-all"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <span className="text-white ml-3 font-semibold text-[15px]">City Map</span>
            <span className="ml-auto text-xs text-white/50 font-medium">{filteredIssues.length} issues</span>
          </div>
          <div className="flex-1">
            <MapContainer
              key="fullscreen-map"
              center={[23.3441, 85.3096]}
              zoom={13}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {filteredIssues.map((issue, idx) => (
                <Marker
                  key={issue.id || idx}
                  position={[issue.location.lat, issue.location.lng]}
                  eventHandlers={{ click: () => navigate(`/issue/${issue.id}`) }}
                  icon={new L.Icon({
                    iconUrl: getMarkerIcon(issue.status),
                    iconSize: [30, 42],
                    iconAnchor: [15, 42],
                    shadowUrl: markerShadow,
                  })}
                >
                  <Popup><b>{issue.title}</b><br />Status: {issue.status}</Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        </motion.div>
      )}

      {/* Bottom Navigation */}
      {!isMapFullscreen && <BottomNavigation />}
    </div>
  );
};

export default Dashboard;