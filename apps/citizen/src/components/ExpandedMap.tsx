import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, MapPin, Filter, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { DepartmentIcon } from './DepartmentIcon';

import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const ExpandedMap: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useApp();
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedIssue, setSelectedIssue] = useState<any>(null);

  const departments = ['all', 'roads', 'sanitation', 'water', 'lighting'];
  const statuses = ['all', 'submitted', 'in-progress', 'resolved'];

  const filteredIssues = state.issues
    .filter(issue => selectedDepartment === 'all' || issue.category === selectedDepartment)
    .filter(issue => selectedStatus === 'all' || issue.status === selectedStatus);

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

  // THIS FUNCTION WAS ADDED TO FIX THE BUG
  const getMarkerColor = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-red-600';
      case 'in-progress': return 'bg-yellow-600';
      case 'resolved': return 'bg-green-600';
      default: return 'bg-gray-500';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'submitted': return 'Submitted';
      case 'in-progress': return 'In Progress';
      case 'resolved': return 'Resolved';
      default: return status;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 relative">
      {/* Header */}
      <div className="bg-white shadow-sm p-4 relative z-20">
        <div className="flex items-center space-x-4 mb-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <h1 className="text-lg font-semibold text-gray-800">Issues Map</h1>
        </div>

        {/* Department Filters */}
        <div className="flex space-x-2 mb-3 overflow-x-auto pb-2">
          {departments.map((dept) => (
            <button
              key={dept}
              onClick={() => setSelectedDepartment(dept)}
              className={`flex items-center space-x-2 px-4 py-2 rounded-full whitespace-nowrap transition-colors ${
                selectedDepartment === dept
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {dept !== 'all' && <DepartmentIcon category={dept as any} size="sm" />}
              <span className="text-sm capitalize">
                {dept === 'all' ? 'All Departments' : dept}
              </span>
            </button>
          ))}
        </div>

        {/* Status Filters */}
        <div className="flex space-x-2 overflow-x-auto pb-2">
          {statuses.map((status) => (
            <button
              key={status}
              onClick={() => setSelectedStatus(status)}
              className={`px-4 py-2 rounded-full text-sm whitespace-nowrap transition-colors ${
                selectedStatus === status
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {status === 'all' ? 'All Status' : getStatusText(status)}
            </button>
          ))}
        </div>
      </div>

      {/* Map Area */}
      <div className="relative z-10">
        <MapContainer
          center={[23.3441, 85.3096]}
          zoom={13}
          style={{ height: 'calc(100vh - 250px)', width: '100%' }}
          scrollWheelZoom={true}
        >
          {/* THE TILELAYER WAS UPDATED FOR THE NEW MAP STYLE */}
          <TileLayer
            attribution='Tiles &copy; Esri &mdash; National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC'
            url='https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}'
          />

          {filteredIssues.map((issue) => (
            <Marker
              key={issue.id}
              position={[issue.location.lat, issue.location.lng]}
              eventHandlers={{
                click: () => setSelectedIssue(issue),
              }}
              icon={new L.Icon({
                iconUrl: getMarkerIcon(issue.status),
                iconSize: [30, 42],
                iconAnchor: [15, 42],
                shadowUrl: markerShadow,
              })}
            />
          ))}

          {/* Floating UI Elements are placed inside the MapContainer */}
          <div className="absolute bottom-6 right-6 z-[1000]">
               <button className="bg-white p-3 rounded-full shadow-lg hover:shadow-xl transition-shadow">
                 <MapPin className="w-6 h-6 text-green-600" />
               </button>
          </div>
          
          <div className="absolute bottom-6 left-6 z-[1000]">
            <div className="bg-white rounded-lg shadow-lg p-4">
              <p className="text-sm text-gray-600 mb-1">Showing Issues</p>
              <p className="text-2xl font-bold text-gray-800">{filteredIssues.length}</p>
            </div>
          </div>
        </MapContainer>
      </div>

      {/* THE LEGEND WAS UPDATED TO SHOW THE REAL MARKERS */}
      <div className="bg-white shadow-sm p-4">
        <div className="flex items-center justify-center space-x-6">
          <div className="flex items-center space-x-2">
            <img src={getMarkerIcon('submitted')} alt="Submitted" className="w-4 h-6" />
            <span className="text-sm text-gray-600">Submitted</span>
          </div>
          <div className="flex items-center space-x-2">
            <img src={getMarkerIcon('in-progress')} alt="In Progress" className="w-4 h-6" />
            <span className="text-sm text-gray-600">In Progress</span>
          </div>
          <div className="flex items-center space-x-2">
            <img src={getMarkerIcon('resolved')} alt="Resolved" className="w-4 h-6" />
            <span className="text-sm text-gray-600">Resolved</span>
          </div>
        </div>
      </div>

      {/* Issue Popup/Modal */}
      {selectedIssue && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          className="fixed inset-x-0 bottom-0 bg-white rounded-t-xl shadow-2xl z-30 max-h-[50vh] overflow-y-auto"
        >
          <div className="p-4">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start space-x-3">
                <DepartmentIcon category={selectedIssue.category} size="md" />
                <div>
                  <h3 className="font-semibold text-gray-800">{selectedIssue.title}</h3>
                  <p className="text-sm text-gray-600 capitalize">{selectedIssue.category}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedIssue(null)}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {selectedIssue.image && (
              <img
                src={selectedIssue.image}
                alt={selectedIssue.title}
                className="w-full h-40 object-cover rounded-lg mb-4"
              />
            )}

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Status</span>
                {/* THIS LINE IS NOW FIXED */}
                <span className={`px-2 py-1 rounded-full text-xs font-medium text-white ${getMarkerColor(selectedIssue.status)}`}>
                  {getStatusText(selectedIssue.status)}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Date</span>
                <span className="text-sm text-gray-800">{selectedIssue.date}</span>
              </div>

              {selectedIssue.landmark && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">Landmark</span>
                  <span className="text-sm text-gray-800">{selectedIssue.landmark}</span>
                </div>
              )}

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Upvotes</span>
                <span className="text-sm text-gray-800">{selectedIssue.upvotes}</span>
              </div>

              <button
                onClick={() => navigate(`/issue/${selectedIssue.id}`)}
                className="w-full mt-4 py-3 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors"
              >
                View Details
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default ExpandedMap;