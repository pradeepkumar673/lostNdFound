// src/pages/HeatmapPage.tsx
import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Map, Layers } from 'lucide-react';
import { statsApi } from '@/lib/api';
import 'leaflet/dist/leaflet.css';

// We lazy-import leaflet to avoid SSR issues
export default function HeatmapPage() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<unknown>(null);

  const { data: heatData } = useQuery({
    queryKey: ['heatmap-data'],
    queryFn: statsApi.heatmap,
  });

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    // Dynamically import leaflet
    import('leaflet').then((L) => {
      if (!mapRef.current) return;

      const map = L.default.map(mapRef.current, {
        center: [12.9716, 77.5946], // Default campus coords (Bangalore)
        zoom: 17,
        zoomControl: true,
        attributionControl: false,
      });

      L.default.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        className: 'map-tiles',
      }).addTo(map);

      mapInstance.current = map;

      // Add sample markers for campus zones
      const zones = [
        { name: 'Main Building', lat: 12.9716, lng: 77.5946 },
        { name: 'Library', lat: 12.9720, lng: 77.5950 },
        { name: 'Cafeteria', lat: 12.9712, lng: 77.5940 },
        { name: 'Sports Complex', lat: 12.9725, lng: 77.5955 },
        { name: 'Hostel Block', lat: 12.9708, lng: 77.5935 },
      ];

      zones.forEach((z) => {
        const marker = L.default.circleMarker([z.lat, z.lng], {
          radius: 12,
          fillColor: '#10b981',
          color: '#10b981',
          weight: 2,
          opacity: 0.8,
          fillOpacity: 0.3,
        }).addTo(map);

        marker.bindPopup(`<strong>${z.name}</strong>`);
      });
    });

    return () => {
      if (mapInstance.current) {
        (mapInstance.current as { remove: () => void }).remove();
        mapInstance.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapInstance.current || !heatData) return;
    // Heatmap layer would be added here with leaflet.heat
    // For now markers are shown
  }, [heatData]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-border/30 flex items-center justify-between">
        <div>
          <h1 className="font-display font-bold text-2xl text-foreground flex items-center gap-2">
            <Map className="w-6 h-6 text-emerald-400" /> Campus Heatmap
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Lost &amp; Found density across campus</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 glass px-3 py-2 rounded-xl border border-border text-xs text-muted-foreground">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span>Lost</span>
          </div>
          <div className="flex items-center gap-2 glass px-3 py-2 rounded-xl border border-border text-xs text-muted-foreground">
            <div className="w-3 h-3 rounded-full bg-emerald-500" />
            <span>Found</span>
          </div>
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <style>{`
          .map-tiles { filter: saturate(0.3) brightness(0.7) hue-rotate(200deg); }
          .leaflet-container { background: hsl(222, 47%, 6%); }
          .leaflet-popup-content-wrapper { background: hsl(222, 47%, 10%); color: hsl(210, 40%, 96%); border: 1px solid hsl(222, 47%, 20%); border-radius: 12px; }
          .leaflet-popup-tip { background: hsl(222, 47%, 10%); }
        `}</style>
        <div ref={mapRef} className="w-full h-full" />

        {/* Legend overlay */}
        <div className="absolute bottom-6 left-6 glass rounded-2xl p-4 border border-white/10 z-[1000] space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <Layers className="w-4 h-4 text-emerald-400" />
            <span>Map Legend</span>
          </div>
          <div className="space-y-1.5 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500" />
              Campus zone
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-1 rounded bg-emerald-500/50" />
              High activity
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
