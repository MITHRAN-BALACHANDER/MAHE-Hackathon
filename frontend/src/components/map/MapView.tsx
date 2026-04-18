"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Coordinate, HeatmapZone, RouteOption } from "@/src/types/route";

const BANGALORE_CENTER: L.LatLngExpression = [12.9716, 77.5946];
const DEFAULT_ZOOM = 12;

const ROUTE_COLORS = {
  selected: "#4285F4",
  alt: "#93b5f5",
} as const;

function createZoneIcon(zone: HeatmapZone): L.DivIcon {
  const color =
    zone.signal_strength === "strong"
      ? "#34A853"
      : zone.signal_strength === "medium"
        ? "#FBBC04"
        : "#EA4335";

  // Cell tower SVG icon
  const towerSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4.9 16.1C1 12.2 1 5.8 4.9 1.9"/>
    <path d="M7.8 4.7a6.14 6.14 0 0 0-.8 7.5"/>
    <circle cx="12" cy="9" r="2"/>
    <path d="M16.2 4.7a6.14 6.14 0 0 1 .8 7.5"/>
    <path d="M19.1 1.9a10.56 10.56 0 0 1 0 14.2"/>
    <path d="M12 11v9"/>
    <path d="M8 20h8"/>
  </svg>`;

  return L.divIcon({
    className: "",
    html: `<div style="
      display:flex;align-items:center;gap:4px;
      background:#fff;
      padding:3px 8px 3px 4px;
      border-radius:16px;
      border:1.5px solid ${color};
      white-space:nowrap;
      box-shadow:0 1px 4px rgba(0,0,0,.15);
      cursor:pointer;
      pointer-events:auto;
    ">${towerSvg}<span style="font-size:10px;font-weight:600;color:${color};">${Math.round(zone.score)}</span></div>`,
    iconAnchor: [45, 14],
  });
}

function createUserIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:18px;height:18px;
      background:#4285F4;
      border:3px solid #fff;
      border-radius:50%;
      box-shadow:0 1px 4px rgba(0,0,0,.4);
    "></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

type Props = {
  routes: RouteOption[];
  selectedRouteIndex: number;
  heatmapZones: HeatmapZone[];
  onRouteClick?: (index: number) => void;
  trackingPosition?: Coordinate | null;
  userLocation?: Coordinate | null;
};

export default function MapView({
  routes,
  selectedRouteIndex,
  heatmapZones,
  onRouteClick,
  trackingPosition,
  userLocation,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const routeLayersRef = useRef<L.Polyline[]>([]);
  const zoneLayerRef = useRef<L.LayerGroup | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const userLocMarkerRef = useRef<L.Marker | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [tilesLoaded, setTilesLoaded] = useState(false);

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

  // Draw routes
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;

    // Clear old
    routeLayersRef.current.forEach((l) => l.remove());
    routeLayersRef.current = [];

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
        color: isSelected ? ROUTE_COLORS.selected : ROUTE_COLORS.alt,
        weight: isSelected ? 6 : 4,
        opacity: isSelected ? 1 : 0.6,
        lineJoin: "round",
        lineCap: "round",
        interactive: true,
        bubblingMouseEvents: false,
      }).addTo(map);

      // Pointer cursor on hover for alt routes
      if (!isSelected) {
        polyline.on("mouseover", () => {
          (polyline as L.Polyline).setStyle({ weight: 6, opacity: 0.85 });
          map.getContainer().style.cursor = "pointer";
        });
        polyline.on("mouseout", () => {
          (polyline as L.Polyline).setStyle({ weight: 4, opacity: 0.6 });
          map.getContainer().style.cursor = "";
        });
      }

      polyline.on("click", () => onRouteClick?.(i));
      routeLayersRef.current.push(polyline);
    });

    // Fit bounds to selected route
    const selected = routes[selectedRouteIndex];
    if (selected?.path.length > 0) {
      const bounds = L.latLngBounds(selected.path.map((p) => [p.lat, p.lng] as L.LatLngExpression));
      map.fitBounds(bounds, { padding: [60, 60] });
    }
  }, [mapReady, routes, selectedRouteIndex, onRouteClick]);

  // Draw zone markers
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;

    if (zoneLayerRef.current) {
      zoneLayerRef.current.clearLayers();
    } else {
      zoneLayerRef.current = L.layerGroup().addTo(map);
    }

    heatmapZones.forEach((zone) => {
      const icon = createZoneIcon(zone);
      const marker = L.marker([zone.lat, zone.lng], { icon, interactive: true });
      marker.bindTooltip(
        `<b>${zone.name}</b><br/>Signal: ${zone.score.toFixed(1)}/100<br/>${zone.signal_strength}`,
        { direction: "top", className: "zone-tooltip" },
      );
      zoneLayerRef.current!.addLayer(marker);
    });
  }, [mapReady, heatmapZones]);

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
        background:#4285F4;
        border:3px solid #fff;
        border-radius:50%;
        box-shadow:0 0 0 2px rgba(66,133,244,.3), 0 1px 4px rgba(0,0,0,.3);
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
        ref={containerRef}
        className="absolute inset-0"
        style={{ zIndex: 0 }}
      />
    </>
  );
}
