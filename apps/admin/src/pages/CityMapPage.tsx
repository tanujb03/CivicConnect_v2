/**
 * A08 — City Map (full page)
 * Operational map with layers: cases, clusters, heatmap, wards,
 * departments, hotspots, SLA risk, recurring locations, active incidents.
 *
 * Data: useMapCases(), useMapHotspots(), useRecurringProblems()
 */
import React, { useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Layers, Filter, MapPin, AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// Fix Leaflet default icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Mock cases — replaced by useMapCases() when backend is ready
const MOCK_CASES = [
  { id: 'CC-1042', lat: 23.344, lng: 85.309, severity: 'CRITICAL', category: 'Roads',      title: 'Major pothole near school' },
  { id: 'CC-1038', lat: 23.355, lng: 85.329, severity: 'HIGH',     category: 'Sanitation', title: 'Sewage overflow residential' },
  { id: 'CC-1031', lat: 23.334, lng: 85.319, severity: 'HIGH',     category: 'Electrical', title: 'Street lighting failure 200m' },
  { id: 'CC-1027', lat: 23.364, lng: 85.339, severity: 'CRITICAL', category: 'Water',      title: 'Water supply disruption' },
  { id: 'CC-1019', lat: 23.324, lng: 85.299, severity: 'MEDIUM',   category: 'Garbage',    title: 'Garbage accumulation market' },
  { id: 'CC-1015', lat: 23.348, lng: 85.315, severity: 'LOW',      category: 'Roads',      title: 'Minor road crack' },
  { id: 'CC-1009', lat: 23.360, lng: 85.305, severity: 'HIGH',     category: 'Roads',      title: 'Road flood prone area' },
];

// Mock hotspots
const MOCK_HOTSPOTS = [
  { id: 'hs-1', lat: 23.344, lng: 85.309, radius: 600, label: 'W12 Road cluster' },
  { id: 'hs-2', lat: 23.355, lng: 85.329, radius: 400, label: 'W18 Sanitation cluster' },
];

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  MEDIUM:   '#eab308',
  LOW:      '#22c55e',
};

function makeIcon(color: string) {
  return new L.DivIcon({
    className: '',
    html: `<div style="background:${color};width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.4)"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

type LayerKey = 'cases' | 'hotspots' | 'recurring';

const CityMapPage: React.FC = () => {
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    cases:     true,
    hotspots:  true,
    recurring: false,
  });
  const [filterSeverity, setFilterSeverity] = useState('ALL');

  const toggleLayer = (k: LayerKey) =>
    setLayers(prev => ({ ...prev, [k]: !prev[k] }));

  const visibleCases = MOCK_CASES.filter(c =>
    filterSeverity === 'ALL' || c.severity === filterSeverity
  );

  return (
    <div className="h-[calc(100vh-72px)] flex flex-col">
      {/* Toolbar */}
      <div className="bg-white border-b border-gray-100 px-5 py-3 flex items-center gap-4 flex-wrap z-10">
        <span className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
          <Layers className="h-4 w-4 text-green-600" /> Map Layers
        </span>

        {(Object.keys(layers) as LayerKey[]).map(k => (
          <button
            key={k}
            onClick={() => toggleLayer(k)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              layers[k]
                ? 'bg-green-100 text-green-800 border-green-300'
                : 'bg-gray-100 text-gray-500 border-gray-200'
            }`}
          >
            {k === 'cases' ? 'Cases' : k === 'hotspots' ? 'Hotspots' : 'Recurring'}
          </button>
        ))}

        <div className="flex items-center gap-2 ml-auto">
          <Filter className="h-3.5 w-3.5 text-gray-400" />
          <span className="text-xs text-gray-500">Severity:</span>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => (
            <button
              key={s}
              onClick={() => setFilterSeverity(s)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                filterSeverity === s
                  ? 'bg-gray-800 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 ml-2">
          <Badge variant="secondary" className="text-xs">
            {visibleCases.length} cases visible
          </Badge>
          <Button size="sm" variant="ghost" className="text-xs">
            <RefreshCw className="h-3.5 w-3.5 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {/* Map + side panel */}
      <div className="flex-1 flex">
        {/* Map */}
        <div className="flex-1 relative z-0">
          <MapContainer
            center={[23.3441, 85.3096]}
            zoom={13}
            scrollWheelZoom
            className="h-full w-full"
            zoomControl
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {/* Case markers */}
            {layers.cases && visibleCases.map(c => (
              <Marker
                key={c.id}
                position={[c.lat, c.lng]}
                icon={makeIcon(SEVERITY_COLORS[c.severity] ?? '#6b7280')}
              >
                <Popup>
                  <div className="text-xs space-y-1 min-w-[180px]">
                    <p className="font-semibold text-gray-800">{c.id}</p>
                    <p className="text-gray-600">{c.title}</p>
                    <div className="flex items-center gap-2">
                      <span
                        className="px-1.5 py-0.5 rounded text-white text-[10px] font-medium"
                        style={{ backgroundColor: SEVERITY_COLORS[c.severity] }}
                      >
                        {c.severity}
                      </span>
                      <span className="text-gray-400">{c.category}</span>
                    </div>
                    <a
                      href={`/cases/${c.id}`}
                      className="text-green-700 hover:underline text-[10px] block"
                    >
                      View case →
                    </a>
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Hotspot circles */}
            {layers.hotspots && MOCK_HOTSPOTS.map(hs => (
              <Circle
                key={hs.id}
                center={[hs.lat, hs.lng]}
                radius={hs.radius}
                pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.12, weight: 1.5 }}
              >
                <Popup>
                  <p className="text-xs font-medium text-red-700">{hs.label}</p>
                  <p className="text-[10px] text-gray-400">Server-computed hotspot</p>
                </Popup>
              </Circle>
            ))}
          </MapContainer>
        </div>

        {/* Side panel — legend + case list */}
        <div className="w-64 bg-white border-l border-gray-100 flex flex-col overflow-hidden">
          {/* Legend */}
          <div className="p-4 border-b border-gray-50">
            <p className="text-xs font-semibold text-gray-600 mb-3">Legend</p>
            <div className="space-y-1.5">
              {Object.entries(SEVERITY_COLORS).map(([sev, col]) => (
                <div key={sev} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full border border-white shadow-sm" style={{ backgroundColor: col }} />
                  <span className="text-xs text-gray-600">{sev}</span>
                </div>
              ))}
              <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-50">
                <div className="w-10 h-3 rounded border-2 border-red-400 bg-red-100 opacity-60" />
                <span className="text-xs text-gray-600">Hotspot cluster</span>
              </div>
            </div>
          </div>

          {/* Visible case list */}
          <div className="flex-1 overflow-y-auto">
            <p className="text-xs font-semibold text-gray-500 px-4 pt-3 pb-2">
              Visible Cases ({visibleCases.length})
            </p>
            {visibleCases.map(c => (
              <a
                key={c.id}
                href={`/cases/${c.id}`}
                className="flex items-start gap-2.5 px-4 py-2.5 hover:bg-gray-50 transition-colors border-b border-gray-50 block"
              >
                <div
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5"
                  style={{ backgroundColor: SEVERITY_COLORS[c.severity] }}
                />
                <div>
                  <p className="text-xs font-medium text-gray-700 leading-tight">{c.title}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5">{c.id} · {c.category}</p>
                </div>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CityMapPage;
