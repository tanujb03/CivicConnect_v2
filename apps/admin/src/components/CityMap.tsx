/**
 * CityMap — Dashboard widget showing a live Leaflet map.
 * Displays color-coded civic issue markers from the active case set.
 * Read-only. Uses react-leaflet + OpenStreetMap tiles.
 */
import React from 'react';
import { MapPin, Layers } from 'lucide-react';
import { MapContainer, TileLayer, CircleMarker, Popup, ZoomControl } from 'react-leaflet';
import L from 'leaflet';

// Fix Leaflet default icon path broken by Vite bundler
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const MOCK_MARKERS = [
  { id: 'CC-1042', title: 'Major pothole near school', lat: 23.3441, lng: 85.3096, priority: 'URGENT', status: 'in_progress', ward: 'W12' },
  { id: 'CC-1038', title: 'Raw sewage overflow',       lat: 23.3520, lng: 85.3190, priority: 'HIGH',   status: 'submitted',   ward: 'W18' },
  { id: 'CC-1031', title: 'Street lighting failure',   lat: 23.3380, lng: 85.3010, priority: 'HIGH',   status: 'submitted',   ward: 'W7'  },
  { id: 'CC-1027', title: 'Water supply disruption',   lat: 23.3480, lng: 85.3250, priority: 'URGENT', status: 'in_progress', ward: 'W3'  },
  { id: 'CC-1019', title: 'Garbage accumulation',      lat: 23.3310, lng: 85.3140, priority: 'NORMAL', status: 'resolved',    ward: 'W9'  },
  { id: 'CC-1015', title: 'Blocked drainage',          lat: 23.3560, lng: 85.3070, priority: 'LOW',    status: 'resolved',    ward: 'W5'  },
  { id: 'CC-1008', title: 'Road crack near market',    lat: 23.3290, lng: 85.2980, priority: 'HIGH',   status: 'in_progress', ward: 'W4'  },
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

const CityMap: React.FC = () => {
  const center: [number, number] = [23.3441, 85.3096];

  return (
    <div className="cc-card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-md border-2 border-ink flex items-center justify-center"
            style={{ background: 'var(--lime-tint)' }}
          >
            <MapPin className="h-3.5 w-3.5 text-ink" />
          </div>
          <div>
            <h3 className="font-display text-sm text-ink">City Map</h3>
            <p className="text-xs font-mono text-muted mt-0.5">Active cases and heat zones</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="cc-chip text-[9px] py-0 px-1.5">Live</span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mb-2">
        {Object.entries(PRIORITY_COLORS).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full border border-black/10" style={{ background: color }} />
            <span className="text-[10px] font-mono text-muted">{label}</span>
          </div>
        ))}
      </div>

      <div
        className="rounded-md border-2 overflow-hidden"
        style={{ height: '320px', borderColor: 'color-mix(in srgb, var(--ink) 15%, transparent)' }}
      >
        <MapContainer
          center={center}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
          scrollWheelZoom={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ZoomControl position="bottomright" />

          {MOCK_MARKERS.map((marker) => (
            <CircleMarker
              key={marker.id}
              center={[marker.lat, marker.lng]}
              radius={marker.priority === 'URGENT' ? 10 : marker.priority === 'HIGH' ? 8 : 6}
              pathOptions={{
                color: PRIORITY_COLORS[marker.priority],
                fillColor: PRIORITY_COLORS[marker.priority],
                fillOpacity: marker.status === 'resolved' ? 0.3 : 0.7,
                weight: 2,
              }}
            >
              <Popup>
                <div style={{ fontFamily: 'Inter, sans-serif', minWidth: '150px' }}>
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
    </div>
  );
};

export default CityMap;