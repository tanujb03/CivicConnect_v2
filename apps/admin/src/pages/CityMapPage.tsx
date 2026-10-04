/**
 * A08 — City Map Page
 * Full-page map view with filter controls and layer toggles.
 * Placeholder until Leaflet tiles + backend geospatial API is wired.
 *
 * Data: /analytics/hotspots, /cases?bounds=lat1,lng1,lat2,lng2
 */
import React, { useState } from 'react';
import { MapPin, Layers, Filter } from 'lucide-react';

const LAYERS = ['Active Cases', 'Heat Zones', 'Work Orders', 'Hotspots'];

const CityMapPage: React.FC = () => {
  const [activeLayers, setActiveLayers] = useState<string[]>(['Active Cases', 'Heat Zones']);

  const toggleLayer = (layer: string) => {
    setActiveLayers(prev =>
      prev.includes(layer) ? prev.filter(l => l !== layer) : [...prev, layer]
    );
  };

  return (
    <div className="space-y-6">
      <div className="cc-page-header">
        <div className="cc-eyebrow cc-fade-up">A08</div>
        <h1 className="cc-title cc-headline-pop">City Map</h1>
      </div>

      {/* Layer toggles */}
      <div className="flex items-center gap-3 cc-fade-up" style={{ '--stagger-index': 0 } as React.CSSProperties}>
        <Filter className="h-4 w-4 text-muted" />
        {LAYERS.map(layer => (
          <button
            key={layer}
            onClick={() => toggleLayer(layer)}
            className={`cc-chip cursor-pointer transition-colors text-[11px] ${
              activeLayers.includes(layer) ? 'bg-lime text-ink border-ink' : 'hover:bg-lime-tint'
            }`}
          >
            {layer}
          </button>
        ))}
      </div>

      {/* Map placeholder */}
      <div className="cc-card overflow-hidden cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
        <div
          className="flex items-center justify-center text-muted"
          style={{
            height: 'calc(100vh - 280px)',
            minHeight: '400px',
            background: 'var(--ground)',
            backgroundImage: 'radial-gradient(circle, var(--dot) 1px, transparent 1px)',
            backgroundSize: '20px 20px',
          }}
        >
          <div className="text-center">
            <Layers className="h-12 w-12 mx-auto mb-3 opacity-20" />
            <p className="font-display text-lg text-ink/30">Full City Map</p>
            <p className="font-mono text-xs mt-2">Map renders when tile server is reachable</p>
            <p className="font-mono text-[10px] mt-1 opacity-50">
              Active layers: {activeLayers.join(', ') || 'None'}
            </p>
          </div>
        </div>
      </div>

      {/* Map legend */}
      <div className="cc-card p-4 cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
        <h3 className="font-display text-sm text-ink mb-3">Legend</h3>
        <div className="flex flex-wrap gap-4">
          {[
            { label: 'Critical', color: 'var(--fire)' },
            { label: 'High', color: 'var(--amber)' },
            { label: 'Normal', color: 'var(--lime)' },
            { label: 'Hotspot', color: 'var(--wine)' },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full border border-ink" style={{ background: item.color }} />
              <span className="text-xs font-mono text-muted">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CityMapPage;
