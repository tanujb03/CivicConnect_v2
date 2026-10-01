import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Bell, Camera, MapPin, TrendingUp, CheckCircle, Clock, ArrowLeft } from 'lucide-react';
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

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useApp();
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');
  const [isMapFullscreen, setIsMapFullscreen] = useState(false); // Fullscreen map state

  const departments = ['all', 'roads', 'sanitation', 'water', 'lighting'];

  const issues = state?.issues || [];
  const filteredIssues =
    selectedDepartment === 'all'
      ? issues
      : issues.filter((issue) => issue.category === selectedDepartment);

  const getMarkerIcon = (status: string) => {
    // Define darker, pointed SVG markers
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
  const mockNews: { id: number; title: string; description: string; image: string; }[] = [
    { id: 1, title: 'City Council Approves New Park Project', description: 'The council has approved a new park project aiming to increase green spaces for residents.', image: 'https://thatssotampa.com/wp-content/uploads/2022/10/BonnetSprings.jpg' },
    { id: 2, title: 'Community Clean-Up Event Scheduled', description: 'Join us for a community clean-up this Saturday at 9 AM. Volunteers are welcome!', image: 'https://tse4.mm.bing.net/th/id/OIP.xHj38LN-gpeIhWzFX7AwKAHaE8?pid=ImgDet&w=194&h=129&c=7&dpr=1.7&o=7&rm=3' },
    { id: 3, title: 'New Traffic Regulations Implemented', description: 'New traffic regulations are now in effect to improve traffic flow and safety. Please review the changes.', image: 'https://images.pexels.com/photos/3972755/pexels-photo-3972755.jpeg?auto=compress&cs=tinysrgb&w=600' },
    { id: 4, title: 'Public Library Expansion Underway', description: 'Construction has begun on the new wing of the central library, expected to open next year.', image: 'https://cdn.fodors.com/wp-content/uploads/2017/09/Public-Libraries-Free-Library-of-Philadelphia-2.jpg' },
    { id: 5, title: 'Annual Water Quality Report Released', description: 'The city has released its annual water quality report, confirming that drinking water is safe.', image: 'https://tse2.mm.bing.net/th/id/OIP.PwpMvv8KnOTBPOOzsA37fwAAAA?rs=1&pid=ImgDetMain&o=7&rm=3' },
    { id: 6, title: 'Road Safety Campaign Launched', description: 'A new campaign aims to increase awareness about pedestrian and cyclist safety on city streets.', image: 'https://th.bing.com/th/id/R.3af6df04e9a2c2fe7ddeb25041d66130?rik=BduDFj%2b%2fGhVlVQ&riu=http%3a%2f%2fblog.trucksuvidha.com%2fwp-content%2fuploads%2f2019%2f02%2fsafety-road-1024x681.jpg&ehk=YJV%2bfDpx4ucrNjnSVMPqWTY%2fE7ifQH%2fUbzgigHCimqI%3d&risl=&pid=ImgRaw&r=0' },
    { id: 7, title: 'Sanitation Department Upgrades Fleet', description: 'New, eco-friendly trucks have been added to the city\'s sanitation fleet.', image: 'https://tse1.mm.bing.net/th/id/OIP.fTdJf3Pe7FMcC4MrGjygyAHaE8?rs=1&pid=ImgDetMain&o=7&rm=3' },
    { id: 8, title: 'Summer Youth Program Registration Open', description: 'Registration for the city\'s summer youth programs is now open for all residents.', image: 'https://as2.ftcdn.net/v2/jpg/04/62/71/27/1000_F_462712750_KQF8xgjMXaeYNzUOoj6v8UaBR9I8kgLT.jpg' },
    { id: 9, title: 'New Streetlights Installed on Main St', description: 'Energy-efficient LED streetlights have been installed along Main Street to improve visibility.', image: 'https://th.bing.com/th/id/OIP.fLXyF7W0vR-w_9IYi8rW-gHaEk?o=7rm=3&rs=1&pid=ImgDetMain&o=7&rm=3' },
    { id: 10, title: 'Recycling Program Expansion Announced', description: 'The curbside recycling program will be expanded to include more types of plastics and glass.', image: 'https://www.rubicon.com/wp-content/uploads/2021/06/cartoon-bin-recycling.png' },
    { id: 11, title: 'Pothole Repair Blitz Planned for Next Week', description: 'Public works crews will conduct a city-wide pothole repair blitz starting Monday.', image: 'https://tse3.mm.bing.net/th/id/OIP.bXqBiZPTSzjK97WAQxbZigHaFj?rs=1&pid=ImgDetMain&o=7&rm=3' },
    { id: 12, title: 'City Museum Offers Free Admission Day', description: 'The city history museum will offer free admission to all visitors this coming Sunday.', image: 'https://tse3.mm.bing.net/th/id/OIP.aKVERLH8t144-qyHejdiIQHaFj?rs=1&pid=ImgDetMain&o=7&rm=3' },
    { id: 13, title: 'New Public Transit Routes Added', description: 'Two new bus routes have been added to serve the north and west sides of the city.', image: 'https://live.staticflickr.com/65535/47981143758_56db29bba9.jpg' },
    { id: 14, title: 'Farmers Market Season Kicks Off', description: 'The downtown farmers market is now open every Saturday from 8 AM to 1 PM.', image: 'https://images.pexels.com/photos/2252584/pexels-photo-2252584.jpeg?auto=compress&cs=tinysrgb&w=600' },
    { id: 15, title: 'Fire Department Hosts Open House', description: 'Meet your local firefighters and learn about fire safety at the open house event next weekend.', image: 'https://th.bing.com/th/id/R.7f25edbe12672d7d322871c175d94fb3?rik=jIgr2fBzQNeOXQ&riu=http%3a%2f%2fclevelandtn.gov%2fImageRepository%2fDocument%3fdocumentId%3d2094&ehk=SGI4iNOJ2lbVTYMnDbl7EnyA6ojH4wwMMrNgfVTAop8%3d&risl=&pid=ImgRaw&r=0' },
  ];

  // Mock Stats
  const mockStats = {
    totalIssues: issues.length,
    resolvedIssues: issues.filter((i) => i.status === 'resolved').length,
    avgResponseTime: '2d 5h',
  };

  return (
    <div className="min-h-screen bg-gray-100 pb-28 relative">
      {!isMapFullscreen && (
        <>
          {/* Top Bar */}
           <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white p-4">
    <div className="flex items-center justify-between">
      <div className="flex items-center space-x-3">
        <div className="w-8 h-8 rounded-full overflow-hidden flex items-center justify-center">
          <img
            src={logo}
            alt="CivicConnect Logo"
            className="w-full h-full object-cover"
          />
        </div>
        <div>
          <p className="text-sm opacity-90">CivicConnect</p>
          <p className="font-semibold">Citizen Dashboard</p>
        </div>
      </div>
      <div className="flex items-center space-x-2">
        <MapPin className="w-4 h-4" />
        <span className="text-sm">Ranchi, Jharkhand</span>
      </div>
      <div className="flex items-center space-x-3">
        <button
          onClick={() => navigate('/notifications')}
          className="relative p-2 hover:bg-white/10 rounded-full transition-colors"
        >
          <Bell className="w-5 h-5" />
          <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full"></div>
        </button>
        <div className="w-8 h-8 rounded-full overflow-hidden">
          <img
            src={
              state.user?.avatar ||
              'https://images.pexels.com/photos/771742/pexels-photo-771742.jpeg?auto=compress&cs=tinysrgb&w=100&h=100&fit=crop'
            }
            alt="Profile"
            className="w-full h-full object-cover"
          />
        </div>
      </div>
    </div>
  </div>
        </>
      )}

      <div className="p-4 space-y-6">
        {/* Map Card */}
        {!isMapFullscreen && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="bg-slate-50 rounded-xl shadow-sm overflow-hidden relative"
          >
            <div className="p-4">
              <h3 className="font-semibold text-gray-800 mb-3">Issues Near You</h3>
            </div>

            {/* Department Filters */}
            <div className="flex space-x-2 px-4 pb-2 overflow-x-auto scrollbar-hide">
              {departments.map((dept) => (
                <button
                  key={dept}
                  onClick={() => setSelectedDepartment(dept)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-full whitespace-nowrap transition-colors ${
                    selectedDepartment === dept
                      ? 'bg-[#1A531A] text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {dept !== 'all' && <DepartmentIcon category={dept as any} size="sm" />}
                  <span className="text-sm capitalize">{dept === 'all' ? 'All Issues' : dept}</span>
                </button>
              ))}
            </div>

            <div
              className="h-64 w-full relative z-0 cursor-pointer"
              onClick={() => setIsMapFullscreen(true)}
            >
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
                    eventHandlers={{
                      click: () => navigate(`/issue/${issue.id}`),
                    }}
                    icon={new L.Icon({
                      iconUrl: getMarkerIcon(issue.status),
                      iconSize: [30, 42],
                      iconAnchor: [15, 42],
                      shadowUrl: markerShadow,
                    })}
                  >
                    <Popup>
                      <b>{issue.title}</b>
                      <br />
                      Status: {issue.status}
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
            </div>
            
            <div className="p-4 border-t bg-gray-50">
              <p className="text-sm text-gray-600">
                Showing {filteredIssues.length} issues • Click markers for details
              </p>
            </div>
          </motion.div>
        )}

        {/* Report Issue Card */}
        {!isMapFullscreen && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            onClick={() => navigate('/report')}
            className="bg-white rounded-xl shadow-sm p-6 cursor-pointer hover:shadow-md transition-shadow"
          >
            <div className="flex items-center justify-center space-x-4">
              <div className="w-16 h-16 bg-[#E8F5E9] rounded-full flex items-center justify-center">
                <Camera className="w-8 h-8 text-[#1A531A]" />
              </div>
              <div className="text-center">
                <h3 className="font-semibold text-gray-800">Report an Issue</h3>
                <p className="text-sm text-gray-600 mt-1">Take a photo and report civic problems</p>
              </div>
            </div>
          </motion.div>
        )}

        {/* Civic News */}
        {!isMapFullscreen && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="space-y-3"
          >
            <h3 className="font-bold text-lg text-gray-800 px-1">Civic News</h3>
            
            <div className="flex space-x-4 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide">
              {mockNews.map((news) => (
                <div
                  key={news.id}
                  className="flex-shrink-0 w-[280px] bg-white rounded-xl shadow-sm overflow-hidden" 
                >
                  <img
                    src={news.image}
                    alt={news.title}
                    className="w-full h-32 object-cover"
                  />
                  <div className="p-3">
                    <h4 className="font-semibold text-base text-gray-900 leading-tight">{news.title}</h4>
                    <p className="text-xs text-gray-600 mt-1 line-clamp-2">{news.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Quick Stats */}
        {!isMapFullscreen && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="space-y-3"
          >
            <h3 className="font-semibold text-gray-800">Quick Stats</h3>
            <div className="flex space-x-4 overflow-x-auto pb-2">
              <div className="flex-shrink-0 bg-white rounded-xl shadow-sm p-4 w-40">
                <div className="flex items-center space-x-2">
                  <TrendingUp className="w-5 h-5 text-blue-600" />
                  <div>
                    <p className="text-2xl font-bold text-gray-800">{mockStats.totalIssues}</p>
                    <p className="text-sm text-gray-600">Total Issues</p>
                  </div>
                </div>
              </div>

              <div className="flex-shrink-0 bg-white rounded-xl shadow-sm p-4 w-40">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-5 h-5 text-[#1A531A]" />
                  <div>
                    <p className="text-2xl font-bold text-gray-800">{mockStats.resolvedIssues}</p>
                    <p className="text-sm text-gray-600">Resolved</p>
                  </div>
                </div>
              </div>

              <div className="flex-shrink-0 bg-white rounded-xl shadow-sm p-4 w-40">
                <div className="flex items-center space-x-2">
                  <Clock className="w-5 h-5 text-orange-600" />
                  <div>
                    <p className="text-2xl font-bold text-gray-800">{mockStats.avgResponseTime}</p>
                    <p className="text-sm text-gray-600">Avg Response</p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Fullscreen Map Modal */}
      {isMapFullscreen && (
        <div className="fixed inset-0 z-50 bg-black flex flex-col">
          <div className="flex items-center p-4">
            <button
              onClick={() => setIsMapFullscreen(false)}
              className="text-white p-2 rounded-full hover:bg-white/20 transition"
            >
              <ArrowLeft className="w-6 h-6" />
            </button>
            <span className="text-white ml-2 font-semibold">Full Screen Map</span>
          </div>
          <div className="flex-1">
            <MapContainer
              key="fullscreen-map" 
              center={[23.3441, 85.3096]}
              zoom={13}
              style={{ height: '100%', width: '100%' }}
            >
              {/* CHANGE: Updated to OpenStreetMap */}
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {filteredIssues.map((issue, idx) => (
                <Marker
                  key={issue.id || idx}
                  position={[issue.location.lat, issue.location.lng]}
                  eventHandlers={{
                    click: () => navigate(`/issue/${issue.id}`),
                  }}
                  icon={new L.Icon({
                    iconUrl: getMarkerIcon(issue.status),
                    iconSize: [30, 42],
                    iconAnchor: [15, 42],
                    shadowUrl: markerShadow,
                  })}
                >
                  <Popup>
                    <b>{issue.title}</b>
                    <br />
                    Status: {issue.status}
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        </div>
      )}

      {/* Bottom Navigation */}
      {!isMapFullscreen && <BottomNavigation />}
    </div>
  );
};

export default Dashboard;