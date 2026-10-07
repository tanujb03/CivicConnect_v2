/**
 * CivicLeafletMap — Shared Leaflet map component for the Overlooker portal.
 * Uses react-leaflet with OpenStreetMap tiles.
 * Displays mock civic issue markers with colour-coded priorities.
 * Read-only — no mutations.
 */
import React, { useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon broken by Vite/webpack bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface CaseMarker {
  id: string;
  title: string;
  lat: number;
  lng: number;
  priority: 'URGENT' | 'HIGH' | 'NORMAL' | 'LOW';
  status: 'in_progress' | 'submitted' | 'resolved';
  ward: string;
}

const MOCK_MARKERS: CaseMarker[] = [
  { id: 'CC-1042', title: 'Major pothole near school', lat: 23.3441, lng: 85.3096, priority: 'URGENT', status: 'in_progress', ward: 'W12' },
  { id: 'CC-1038', title: 'Raw sewage overflow', lat: 23.3520, lng: 85.3190, priority: 'HIGH', status: 'submitted', ward: 'W18' },
  { id: 'CC-1031', title: 'Street lighting failure', lat: 23.3380, lng: 85.3010, priority: 'HIGH', status: 'submitted', ward: 'W7' },
  { id: 'CC-1027', title: 'Water supply disruption', lat: 23.3480, lng: 85.3250, priority: 'URGENT', status: 'in_progress', ward: 'W3' },
  { id: 'CC-1019', title: 'Garbage accumulation', lat: 23.3310, lng: 85.3140, priority: 'NORMAL', status: 'resolved', ward: 'W9' },
  { id: 'CC-1015', title: 'Blocked drainage', lat: 23.3560, lng: 85.3070, priority: 'LOW', status: 'resolved', ward: 'W5' },
  { id: 'CC-1008', title: 'Road crack near market', lat: 23.3290, lng: 85.2980, priority: 'HIGH', status: 'in_progress', ward: 'W4' },
  { id: 'CC-0997', title: 'Broken footpath', lat: 23.3600, lng: 85.3200, priority: 'NORMAL', status: 'submitted', ward: 'W11' },
];

const PRIORITY_COLORS: Record<string, string> = {
  URGENT: '#c0392b',
  HIGH:   '#e67e22',
  NORMAL: '#27ae60',
  LOW:    '#95a5a6',
};

const STATUS_LABELS: Record<string, string> = {
  in_progress: 'In Progress',
  submitted: 'Submitted',
  resolved: 'Resolved',
};

interface CivicLeafletMapProps {
  height?: string;
  className?: string;
  /** If true, render a condensed version (e.g. for the home page widget) */
  compact?: boolean;
}

const CivicLeafletMap: React.FC<CivicLeafletMapProps> = ({ height = '320px', className = '', compact = false }) => {
  // Ranchi city centre
  const center: [number, number] = [23.3441, 85.3096];

  return (
    <div
      className={`rounded-md border-2 overflow-hidden ${className}`}
      style={{ height, borderColor: 'color-mix(in srgb, var(--ink) 15%, transparent)' }}
    >
      <MapContainer
        center={center}
        zoom={compact ? 13 : 14}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
        attributionControl={!compact}
        scrollWheelZoom={!compact}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {!compact && <ZoomControl position="bottomright" />}

        {MOCK_MARKERS.map((marker) => (
          <CircleMarker
            key={marker.id}
            center={[marker.lat, marker.lng]}
            radius={marker.priority === 'URGENT' ? 10 : marker.priority === 'HIGH' ? 8 : 6}
            pathOptions={{
              color: PRIORITY_COLORS[marker.priority],
              fillColor: PRIORITY_COLORS[marker.priority],
              fillOpacity: marker.status === 'resolved' ? 0.35 : 0.75,
              weight: 2,
            }}
          >
            <Popup>
              <div style={{ fontFamily: 'Inter, sans-serif', minWidth: '160px' }}>
                <div style={{ fontSize: '10px', color: '#666', fontFamily: 'monospace', marginBottom: '2px' }}>
                  {marker.id} · {marker.ward}
                </div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#111', marginBottom: '4px' }}>
                  {marker.title}
                </div>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <span style={{
                    display: 'inline-block',
                    padding: '1px 6px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 700,
                    background: PRIORITY_COLORS[marker.priority],
                    color: '#fff',
                  }}>
                    {marker.priority}
                  </span>
                  <span style={{ fontSize: '10px', color: '#666' }}>{STATUS_LABELS[marker.status]}</span>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
};

export default CivicLeafletMap;
