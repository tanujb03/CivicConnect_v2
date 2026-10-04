/**
 * CityMap — Dashboard widget showing a map placeholder.
 * When Leaflet tiles are available, this renders an actual map.
 * For now shows a styled placeholder with the dot-grid background.
 */
import React from 'react';
import { MapPin, Layers } from 'lucide-react';

const CityMap: React.FC = () => {
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
      <div
        className="rounded-md border-2 border-dot flex items-center justify-center text-muted"
        style={{
          height: '320px',
          background: 'var(--ground)',
          backgroundImage: 'radial-gradient(circle, var(--dot) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }}
      >
        <div className="text-center">
          <Layers className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="font-mono text-xs">Map renders when tile server is reachable</p>
          <p className="font-mono text-[10px] mt-1 opacity-50">Leaflet + OpenStreetMap tiles</p>
        </div>
      </div>
    </div>
  );
};

export default CityMap;