"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import {
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
} from "react-leaflet";

import type { HeatmapZone, RouteOption } from "@/src/types/route";

delete (L.Icon.Default.prototype as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const ROUTE_COLORS = ["#22d3ee", "#facc15", "#34d399"];

type RouteMapClientProps = {
  routes: RouteOption[];
  heatmapZones: HeatmapZone[];
};

export default function RouteMapClient({
  routes,
  heatmapZones,
}: RouteMapClientProps) {
  const center: [number, number] = [12.9716, 77.5946];

  return (
    <section className="rounded-2xl border border-white/10 bg-[#0f1b2d] p-2">
      <div className="h-95 overflow-hidden rounded-xl">
        <MapContainer
          center={center}
          zoom={11}
          scrollWheelZoom
          className="h-full w-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {routes.map((route, index) => (
            <Polyline
              key={route.name}
              positions={route.path.map((point) => [point.lat, point.lng])}
              pathOptions={{
                color: ROUTE_COLORS[index % ROUTE_COLORS.length],
                weight: 5,
                opacity: 0.82,
              }}
            >
              <Popup>
                <p className="font-semibold">{route.name}</p>
                <p>ETA: {route.eta} min</p>
                <p>Signal: {route.signal_score}</p>
              </Popup>
            </Polyline>
          ))}

          {heatmapZones.map((zone) => (
            <Marker key={zone.name} position={[zone.lat, zone.lng]}>
              <Tooltip>
                {zone.name}: {zone.signal_strength} ({zone.score})
              </Tooltip>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </section>
  );
}
