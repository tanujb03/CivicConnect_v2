import React, { useEffect, useRef, useState } from 'react';
import { MapPin, X } from 'lucide-react';

// Define the interface for issue markers
interface IssueMarker {
  id: string;
  lat: number;
  lng: number;
  status: 'submitted' | 'progress' | 'resolved';
  location: string;
  category: string;
  details: string;
}

// Mock issues data with real coordinates (using Ranchi, India as reference)
const mockIssues: IssueMarker[] = [
  { id: 'CC001', lat: 23.3441, lng: 85.3096, status: 'submitted', location: 'MG Road', category: 'roads', details: 'Large pothole blocking traffic' },
  { id: 'CC002', lat: 23.3553, lng: 85.3346, status: 'progress', location: 'Station Road', category: 'electrical', details: 'Street light not working' },
  { id: 'CC003', lat: 23.3620, lng: 85.3200, status: 'resolved', location: 'Civil Lines', category: 'sanitation', details: 'Drainage blockage cleared' },
  { id: 'CC004', lat: 23.3380, lng: 85.3280, status: 'submitted', location: 'Main Market', category: 'sanitation', details: 'Garbage overflow' },
  { id: 'CC005', lat: 23.3470, lng: 85.3150, status: 'progress', location: 'Park Street', category: 'roads', details: 'Road construction ongoing' },
  { id: 'CC006', lat: 23.3510, lng: 85.3400, status: 'resolved', location: 'City Center', category: 'electrical', details: 'Power issue fixed' },
  { id: 'CC007', lat: 23.3450, lng: 85.3105, status: 'submitted', location: 'Lake Road', category: 'water', details: 'Water pipe leak' },
  { id: 'CC008', lat: 23.3567, lng: 85.3120, status: 'progress', location: 'Sector 3', category: 'water', details: 'Low water pressure' },
  { id: 'CC009', lat: 23.3350, lng: 85.3190, status: 'resolved', location: 'Market Square', category: 'lighting', details: 'Park lights are now on' },
  { id: 'CC010', lat: 23.3410, lng: 85.3050, status: 'submitted', location: 'Ring Road', category: 'roads', details: 'New pothole reported' },
];

const CityMap: React.FC = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<IssueMarker | null>(null);
  const [leafletLoaded, setLeafletLoaded] = useState(false);
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');

  const departments = ['all', 'roads', 'sanitation', 'water', 'lighting', 'electrical'];
  const filteredIssues =
    selectedDepartment === 'all'
      ? mockIssues
      : mockIssues.filter((issue) => issue.category === selectedDepartment);

  // Load Leaflet dynamically
  useEffect(() => {
    const loadLeaflet = async () => {
      if (window.L) {
        setLeafletLoaded(true);
        return;
      }
      const leafletCSS = document.createElement('link');
      leafletCSS.rel = 'stylesheet';
      leafletCSS.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';
      document.head.appendChild(leafletCSS);

      const leafletJS = document.createElement('script');
      leafletJS.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
      
      leafletJS.onload = () => {
        setLeafletLoaded(true);
      };
      
      leafletJS.onerror = () => {
        console.error('Failed to load Leaflet');
      };
      document.head.appendChild(leafletJS);
    };
    loadLeaflet();
  }, []);

  // New function to get icon based on category
  const getCategoryIcon = (category: string) => {
    let color: string;
    let iconText: string;
    switch (category) {
      case 'roads':
        color = '#E53E3E'; // Red
        iconText = 'R';
        break;
      case 'sanitation':
        color = '#4A5568'; // Dark Gray
        iconText = 'S';
        break;
      case 'water':
        color = '#3182CE'; // Blue
        iconText = 'W';
        break;
      case 'lighting':
        color = '#ECC94B'; // Yellow
        iconText = 'L';
        break;
      case 'electrical':
        color = '#805AD5'; // Purple
        iconText = 'E';
        break;
      default:
        color = '#A0AEC0'; // Light Gray
        iconText = '?';
        break;
    }
    return window.L.divIcon({
      className: 'custom-icon',
      html: `
        <div style="
          background-color: ${color};
          color: white;
          width: 30px;
          height: 30px;
          line-height: 30px;
          text-align: center;
          font-weight: bold;
          border-radius: 50%;
          border: 2px solid white;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          font-size: 14px;
        ">${iconText}</div>
      `,
      iconSize: [30, 30],
      iconAnchor: [15, 30]
    });
  };

  // Initialize and update map based on filters
  useEffect(() => {
    if (!leafletLoaded || !mapRef.current) return;

    if (!mapInstanceRef.current) {
      const L = window.L;
      const map = L.map(mapRef.current).setView([23.3441, 85.3096], 13);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
      }).addTo(map);
      mapInstanceRef.current = map;
    }

    const map = mapInstanceRef.current;
    
    // Clear existing markers
    markersRef.current.forEach(marker => map.removeLayer(marker));
    markersRef.current = [];

    // Add new markers for filtered issues
    filteredIssues.forEach((issue) => {
      const marker = window.L.marker([issue.lat, issue.lng], { icon: getCategoryIcon(issue.category) })
        .addTo(map)
        .on('click', () => {
          setSelectedIssue(issue);
        });
      markersRef.current.push(marker);
    });

  }, [leafletLoaded, selectedDepartment, filteredIssues]);

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-blue-100 text-blue-800';
      case 'progress': return 'bg-yellow-100 text-yellow-800';
      case 'resolved': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (!leafletLoaded) {
    return (
      <div className="bg-white p-6 mb-8 rounded-lg shadow-sm border border-gray-200">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Interactive City Map - Real-time Issue Reports</h3>
        </div>
        <div className="bg-gray-100 h-96 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">Loading map...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-6 mb-8 rounded-lg shadow-sm border border-gray-200">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Interactive City Map - Real-time Issue Reports</h3>
      </div>
      
      {/* Department Filters */}
      <div className="flex space-x-2 px-4 pb-2 mb-4 overflow-x-auto scrollbar-hide">
        {departments.map((dept) => (
          <button
            key={dept}
            onClick={() => {
              setSelectedDepartment(dept);
              setSelectedIssue(null); // Close the popup when the filter changes
            }}
            className={`flex items-center space-x-2 px-4 py-2 rounded-full whitespace-nowrap transition-colors ${
              selectedDepartment === dept
                ? 'bg-gray-800 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            <span className="text-sm capitalize">{dept === 'all' ? 'All Issues' : dept}</span>
          </button>
        ))}
      </div>

      <div className="relative rounded-lg overflow-hidden border border-gray-200">
        {/* Map Container */}
        <div 
          ref={mapRef} 
          className="h-96 w-full z-0"
          style={{ height: '400px' }}
        />

        {/* Issue Details Popup */}
        {selectedIssue && (
          <div className="absolute top-4 right-4 bg-white p-4 rounded-lg shadow-lg border border-gray-200 w-64 z-[1000]">
            <div className="flex justify-between items-start mb-3">
              <h4 className="font-semibold text-gray-900">{selectedIssue.id}</h4>
              <button 
                onClick={() => setSelectedIssue(null)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="h-4 w-4 text-gray-500" />
              </button>
            </div>
            <div className="space-y-2 text-sm">
              <p><strong className="text-gray-700">Location:</strong> <span className="text-gray-600">{selectedIssue.location}</span></p>
              <p><strong className="text-gray-700">Category:</strong> <span className="text-gray-600">{selectedIssue.category}</span></p>
              <div className="flex items-center">
                <strong className="text-gray-700">Status:</strong>
                <span className={`ml-2 px-2 py-1 rounded-full text-xs ${getStatusBadgeClass(selectedIssue.status)}`}>
                  {selectedIssue.status.charAt(0).toUpperCase() + selectedIssue.status.slice(1)}
                </span>
              </div>
              <p><strong className="text-gray-700">Details:</strong> <span className="text-gray-600">{selectedIssue.details}</span></p>
              <div className="flex space-x-2 pt-3">
                <button className="px-3 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 transition-colors">
                  View
                </button>
                <button className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors">
                  Edit
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex justify-center space-x-6 mt-4 text-sm">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full bg-red-600 flex items-center justify-center text-white font-bold text-xs">R</div>
          <span className="text-gray-600">Roads</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full bg-gray-700 flex items-center justify-center text-white font-bold text-xs">S</div>
          <span className="text-gray-600">Sanitation</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-xs">W</div>
          <span className="text-gray-600">Water</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full bg-yellow-400 flex items-center justify-center text-white font-bold text-xs">L</div>
          <span className="text-gray-600">Lighting</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full bg-purple-600 flex items-center justify-center text-white font-bold text-xs">E</div>
          <span className="text-gray-600">Electrical</span>
        </div>
      </div>
    </div>
  );
};

export default CityMap;