"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Coordinate, HeatmapZone, RouteOption, TowerMarker } from "@/src/types/route";

const BANGALORE_CENTER: L.LatLngExpression = [12.9716, 77.5946];
const DEFAULT_ZOOM = 12;

const ROUTE_COLORS = {
  selected: "#3b82f6",
  alt: "#93b5f5",
} as const;

// Distinct colors for each alternative route so all paths are visually separable
const ROUTE_ALT_PALETTE = [
  "#93b5f5",  // light blue
  "#4ade80",  // green
  "#fb923c",  // orange
  "#c084fc",  // purple
  "#34d399",  // emerald
  "#f472b6",  // pink
];

function getRouteColor(index: number, selectedIndex: number): string {
  if (index === selectedIndex) return ROUTE_COLORS.selected;
  // Map each non-selected route to its own palette slot
  const altPos = index < selectedIndex ? index : index - 1;
  return ROUTE_ALT_PALETTE[altPos % ROUTE_ALT_PALETTE.length];
}

export type HeatmapFilterType = "signal" | "weather" | "traffic" | "road";

const HEATMAP_COLORS: Record<HeatmapFilterType, { strong: string; medium: string; weak: string }> = {
  signal: { strong: "#22c55e", medium: "#eab308", weak: "#ef4444" },
  weather: { strong: "#6366f1", medium: "#a78bfa", weak: "#c4b5fd" },
  traffic: { strong: "#22c55e", medium: "#f97316", weak: "#ef4444" },
  road: { strong: "#10b981", medium: "#fbbf24", weak: "#f87171" },
};

// Lucide TowerControl SVG for cell tower markers
function createZoneIcon(zone: HeatmapZone, filterType: HeatmapFilterType = "signal"): L.DivIcon {
  const palette = HEATMAP_COLORS[filterType];
  const color =
    zone.signal_strength === "strong"
      ? palette.strong
      : zone.signal_strength === "medium"
        ? palette.medium
        : palette.weak;

  // Lucide TowerControl icon SVG
  const towerSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M11 12h2"/>
    <path d="M12 12v9"/>
    <path d="M7.5 7.2C6.6 8.3 6 9.6 6 11a6 6 0 0 0 .5 2.4"/>
    <path d="M16.5 7.2c.9 1.1 1.5 2.4 1.5 3.8a6 6 0 0 1-.5 2.4"/>
    <path d="M4.2 4.2C2.8 5.8 2 8.3 2 11c0 1.8.5 3.5 1.2 5"/>
    <path d="M19.8 4.2c1.4 1.6 2.2 4.1 2.2 6.8 0 1.8-.5 3.5-1.2 5"/>
    <path d="M8 21h8"/>
  </svg>`;

  return L.divIcon({
    className: "",
    html: `<div style="
      display:flex;align-items:center;gap:4px;
      background:#fff;
      padding:3px 8px 3px 5px;
      border-radius:16px;
      border:1.5px solid ${color};
      white-space:nowrap;
      box-shadow:0 2px 8px rgba(0,0,0,.12);
      cursor:pointer;
      pointer-events:auto;
      transition: transform 0.15s ease;
    " onmouseover="this.style.transform='scale(1.08)'" onmouseout="this.style.transform='scale(1)'">${towerSvg}<span style="font-size:10px;font-weight:700;color:${color};">${Math.round(zone.score)}</span></div>`,
    iconAnchor: [45, 14],
  });
}

function createPinIcon(type: "source" | "destination"): L.DivIcon {
  const color = type === "source" ? "#3b82f6" : "#ef4444";
  const label = type === "source" ? "A" : "B";
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;cursor:grab;">
      <svg width="36" height="48" viewBox="0 0 36 48">
        <path d="M18 0C8.06 0 0 8.06 0 18c0 12.6 18 30 18 30s18-17.4 18-30C36 8.06 27.94 0 18 0z" fill="${color}"/>
        <circle cx="18" cy="18" r="10" fill="white"/>
        <text x="18" y="23" text-anchor="middle" font-size="14" font-weight="bold" fill="${color}">${label}</text>
      </svg>
    </div>`,
    iconSize: [36, 48],
    iconAnchor: [18, 48],
  });
}

function createUserIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:18px;height:18px;
      background:#3b82f6;
      border:3px solid #fff;
      border-radius:50%;
      box-shadow:0 1px 4px rgba(0,0,0,.4);
    "></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

const OPERATOR_COLORS: Record<string, string> = {
  Jio: "#0070f3",
  Airtel: "#e53e3e",
  Vi: "#d69e2e",
  BSNL: "#38a169",
};

function createTowerDotIcon(tower: TowerMarker): L.DivIcon {
  const color = OPERATOR_COLORS[tower.operator] ?? "#6b7280";
  const size = tower.signal_score >= 70 ? 8 : tower.signal_score >= 40 ? 7 : 6;
  const opacity = tower.signal_score >= 70 ? 0.9 : tower.signal_score >= 40 ? 0.75 : 0.6;
  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px;height:${size}px;
      background:${color};
      border:1.5px solid rgba(255,255,255,0.8);
      border-radius:50%;
      opacity:${opacity};
      box-shadow:0 1px 3px rgba(0,0,0,.25);
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

type Props = {
  routes: RouteOption[];
  selectedRouteIndex: number;
  heatmapZones: HeatmapZone[];
  towerMarkers?: TowerMarker[];
  onRouteClick?: (index: number) => void;
  trackingPosition?: Coordinate | null;
  userLocation?: Coordinate | null;
  heatmapFilter?: HeatmapFilterType;
  onPinDrag?: (type: "source" | "destination", lat: number, lng: number) => void;
};

export default function MapView({
  routes,
  selectedRouteIndex,
  heatmapZones,
  towerMarkers,
  onRouteClick,
  trackingPosition,
  userLocation,
  heatmapFilter = "signal",
  onPinDrag,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const routeLayersRef = useRef<L.Polyline[]>([]);
  const zoneLayerRef = useRef<L.LayerGroup | null>(null);
  const towerLayerRef = useRef<L.LayerGroup | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const userLocMarkerRef = useRef<L.Marker | null>(null);
  const pinLayerRef = useRef<L.LayerGroup | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [tilesLoaded, setTilesLoaded] = useState(false);

  const handlePinDrag = useCallback(
    (type: "source" | "destination", e: L.DragEndEvent) => {
      const latlng = e.target.getLatLng();
      onPinDrag?.(type, latlng.lat, latlng.lng);
    },
    [onPinDrag],
  );

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: BANGALORE_CENTER,
      zoom: DEFAULT_ZOOM,
      zoomControl: false,
      attributionControl: false,
    });

    const tileLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19,
    }).addTo(map);

    tileLayer.on("load", () => setTilesLoaded(true));

    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control.attribution({ position: "bottomright", prefix: false }).addTo(map);

    mapRef.current = map;
    setMapReady(true);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Draw routes with tooltips + source/dest pins
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;

    // Clear old route polylines
    routeLayersRef.current.forEach((l) => l.remove());
    routeLayersRef.current = [];

    // Clear old pin markers
    if (pinLayerRef.current) {
      pinLayerRef.current.clearLayers();
    } else {
      pinLayerRef.current = L.layerGroup().addTo(map);
    }

    if (routes.length === 0) return;

    // Draw alt routes first (behind), then selected on top
    const order = routes
      .map((_, i) => i)
      .sort((a, b) => {
        if (a === selectedRouteIndex) return 1;
        if (b === selectedRouteIndex) return -1;
        return 0;
      });

    order.forEach((i) => {
      const route = routes[i];
      const isSelected = i === selectedRouteIndex;
      const latlngs: L.LatLngExpression[] = route.path.map((p) => [p.lat, p.lng]);

      const polyline = L.polyline(latlngs, {
        color: getRouteColor(i, selectedRouteIndex),
        weight: isSelected ? 6 : 4,
        opacity: isSelected ? 1 : 0.65,
        lineJoin: "round",
        lineCap: "round",
        interactive: true,
        bubblingMouseEvents: false,
      }).addTo(map);

      // Route tooltip with description
      const signalLabel = route.signal_score >= 70 ? "Strong" : route.signal_score >= 40 ? "Medium" : "Weak";
      const tooltipContent = `
        <div style="font-family:system-ui;min-width:160px;">
          <div style="font-weight:700;font-size:13px;margin-bottom:4px;">${route.name}</div>
          <div style="display:flex;gap:12px;font-size:11px;color:#6b7280;">
            <span>⏱ ${route.eta} min</span>
            <span>📍 ${route.distance} km</span>
          </div>
          <div style="margin-top:4px;font-size:11px;">
            Signal: <span style="font-weight:600;color:${route.signal_score >= 70 ? '#22c55e' : route.signal_score >= 40 ? '#eab308' : '#ef4444'}">${signalLabel} (${Math.round(route.signal_score)})</span>
          </div>
          ${route.zones.length > 0 ? `<div style="margin-top:4px;font-size:10px;color:#9ca3af;">via ${route.zones.slice(0, 3).join(", ")}${route.zones.length > 3 ? "..." : ""}</div>` : ""}
        </div>
      `;

      polyline.bindTooltip(tooltipContent, {
        sticky: true,
        direction: "top",
        className: "zone-tooltip",
        offset: [0, -8],
      });

      // Pointer cursor on hover for alt routes
      if (!isSelected) {
        const altColor = getRouteColor(i, selectedRouteIndex);
        polyline.on("mouseover", () => {
          (polyline as L.Polyline).setStyle({ weight: 6, opacity: 0.9, color: altColor });
          map.getContainer().style.cursor = "pointer";
        });
        polyline.on("mouseout", () => {
          (polyline as L.Polyline).setStyle({ weight: 4, opacity: 0.65, color: altColor });
          map.getContainer().style.cursor = "";
        });
      }

      polyline.on("click", () => onRouteClick?.(i));
      routeLayersRef.current.push(polyline);
    });

    // Add draggable source and destination pins for selected route
    const selected = routes[selectedRouteIndex];
    if (selected?.path.length > 0) {
      const startPt = selected.path[0];
      const endPt = selected.path[selected.path.length - 1];

      // Source pin (draggable)
      const srcMarker = L.marker([startPt.lat, startPt.lng], {
        icon: createPinIcon("source"),
        draggable: true,
        zIndexOffset: 500,
      });
      srcMarker.bindTooltip("Drag to adjust start", { direction: "top" });
      srcMarker.on("dragend", (e) => handlePinDrag("source", e as L.DragEndEvent));
      pinLayerRef.current!.addLayer(srcMarker);

      // Destination pin (draggable)
      const dstMarker = L.marker([endPt.lat, endPt.lng], {
        icon: createPinIcon("destination"),
        draggable: true,
        zIndexOffset: 500,
      });
      dstMarker.bindTooltip("Drag to adjust destination", { direction: "top" });
      dstMarker.on("dragend", (e) => handlePinDrag("destination", e as L.DragEndEvent));
      pinLayerRef.current!.addLayer(dstMarker);

      // Fit bounds
      const bounds = L.latLngBounds(selected.path.map((p) => [p.lat, p.lng] as L.LatLngExpression));
      map.fitBounds(bounds, { padding: [60, 60] });
    }
  }, [mapReady, routes, selectedRouteIndex, onRouteClick, handlePinDrag]);

  // Zone badge markers removed -- individual tower dots are used instead
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    if (zoneLayerRef.current) {
      zoneLayerRef.current.clearLayers();
    }
  }, [mapReady, heatmapZones, heatmapFilter]);

  // Draw individual tower dots at real OpenCelliD lat/lng
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;

    if (towerLayerRef.current) {
      towerLayerRef.current.clearLayers();
    } else {
      towerLayerRef.current = L.layerGroup().addTo(map);
    }

    if (!towerMarkers || towerMarkers.length === 0) return;

    towerMarkers.forEach((tower) => {
      const icon = createTowerDotIcon(tower);
      const marker = L.marker([tower.lat, tower.lng], { icon, interactive: true });
      const signalLabel = tower.signal_score >= 70 ? "Strong" : tower.signal_score >= 40 ? "Medium" : "Weak";
      marker.bindTooltip(
        `<b>${tower.operator}</b>${tower.zone ? ` — ${tower.zone}` : ""}<br/>Signal: ${signalLabel} (${Math.round(tower.signal_score)})<br/><span style="font-size:10px;color:#9ca3af;">${tower.tower_id}</span>`,
        { direction: "top", className: "zone-tooltip" },
      );
      towerLayerRef.current!.addLayer(marker);
    });
  }, [mapReady, towerMarkers]);

  // Live tracking marker
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;

    if (!trackingPosition) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }

    if (!markerRef.current) {
      markerRef.current = L.marker([trackingPosition.lat, trackingPosition.lng], {
        icon: createUserIcon(),
        zIndexOffset: 1000,
      }).addTo(mapRef.current);
    } else {
      markerRef.current.setLatLng([trackingPosition.lat, trackingPosition.lng]);
    }
  }, [mapReady, trackingPosition]);

  // User real location marker
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;

    if (!userLocation) {
      userLocMarkerRef.current?.remove();
      userLocMarkerRef.current = null;
      return;
    }

    const icon = L.divIcon({
      className: "",
      html: `<div style="
        width:14px;height:14px;
        background:#3b82f6;
        border:3px solid #fff;
        border-radius:50%;
        box-shadow:0 0 0 2px rgba(59,130,244,.3), 0 1px 4px rgba(0,0,0,.3);
      "></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });

    if (!userLocMarkerRef.current) {
      userLocMarkerRef.current = L.marker([userLocation.lat, userLocation.lng], {
        icon,
        zIndexOffset: 900,
      }).addTo(mapRef.current);
      userLocMarkerRef.current.bindTooltip("Your location", { direction: "top" });
    } else {
      userLocMarkerRef.current.setLatLng([userLocation.lat, userLocation.lng]);
    }
  }, [mapReady, userLocation]);

  return (
    <>
      {!tilesLoaded && (
        <div className="absolute inset-0 z-10 bg-gray-50 flex flex-col items-center justify-center gap-4">
          <div className="w-10 h-10 border-3 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
          <p className="text-sm text-gray-400">Loading map...</p>
        </div>
      )}
      <div
        id="map-area"
        ref={containerRef}
        className="absolute inset-0"
        style={{ zIndex: 0 }}
      />
    </>
  );
}
