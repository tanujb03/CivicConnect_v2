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
  { id: 'CC001', lat: 23.3441, lng: 85.3096, status: 'submitted', location: 'MG Road', category: 'Roads', details: 'Large pothole blocking traffic' },
  { id: 'CC002', lat: 23.3553, lng: 85.3346, status: 'progress', location: 'Station Road', category: 'Electrical', details: 'Street light not working' },
  { id: 'CC003', lat: 23.3620, lng: 85.3200, status: 'resolved', location: 'Civil Lines', category: 'Sanitation', details: 'Drainage blockage cleared' },
  { id: 'CC004', lat: 23.3380, lng: 85.3280, status: 'submitted', location: 'Main Market', category: 'Garbage', details: 'Garbage overflow' },
  { id: 'CC005', lat: 23.3470, lng: 85.3150, status: 'progress', location: 'Park Street', category: 'Roads', details: 'Road construction ongoing' },
  { id: 'CC006', lat: 23.3510, lng: 85.3400, status: 'resolved', location: 'City Center', category: 'Electrical', details: 'Power issue fixed' },
];

const CityMap: React.FC = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<IssueMarker | null>(null);
  const [leafletLoaded, setLeafletLoaded] = useState(false);

  // Load Leaflet dynamically
  useEffect(() => {
    const loadLeaflet = async () => {
      // Check if Leaflet is already loaded
      if (window.L) {
        setLeafletLoaded(true);
        return;
      }

      // Create and load CSS
      const leafletCSS = document.createElement('link');
      leafletCSS.rel = 'stylesheet';
      leafletCSS.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';
      document.head.appendChild(leafletCSS);

      // Create and load JS
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

  // Initialize map when Leaflet is loaded
  useEffect(() => {
    if (!leafletLoaded || !mapRef.current || mapInstanceRef.current) return;

    const L = window.L;
    
    // Initialize map centered on Ranchi, India
    const map = L.map(mapRef.current).setView([23.3441, 85.3096], 13);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    mapInstanceRef.current = map;

    // Add markers for each issue
    mockIssues.forEach((issue) => {
      const markerColor = getMarkerColor(issue.status);
      
      // Create custom icon
      const customIcon = L.divIcon({
        className: 'custom-marker',
        html: `
          <div style="
            width: 24px; 
            height: 24px; 
            background-color: ${markerColor}; 
            border: 3px solid white; 
            border-radius: 50%; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            position: relative;
          ">
            <div style="
              position: absolute;
              top: -8px;
              left: 50%;
              transform: translateX(-50%);
              width: 0;
              height: 0;
              border-left: 6px solid transparent;
              border-right: 6px solid transparent;
              border-bottom: 8px solid ${markerColor};
            "></div>
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 24]
      });

      const marker = L.marker([issue.lat, issue.lng], { icon: customIcon })
        .addTo(map)
        .on('click', () => {
          setSelectedIssue(issue);
        });

      markersRef.current.push(marker);
    });

    // Cleanup function
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
      markersRef.current = [];
    };
  }, [leafletLoaded]);

  const getMarkerColor = (status: string) => {
    switch (status) {
      case 'submitted': return '#3b82f6'; // blue
      case 'progress': return '#eab308'; // yellow
      case 'resolved': return '#10b981'; // green
      default: return '#6b7280'; // gray
    }
  };

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
          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
          <span className="text-gray-600">Submitted</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
          <span className="text-gray-600">In Progress</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          <span className="text-gray-600">Resolved</span>
        </div>
      </div>
    </div>
  );
};

export default CityMap;