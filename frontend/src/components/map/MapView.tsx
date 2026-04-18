"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import type { Coordinate, RouteOption, TowerMarker } from "@/src/types/route";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const BANGALORE_CENTER: [number, number] = [77.5946, 12.9716]; // [lng, lat]
const DEFAULT_ZOOM = 12;
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

const ROUTE_COLORS = {
  selected: "#3b82f6",
} as const;

const ROUTE_ALT_PALETTE = [
  "#94a3b8", // slate
  "#4ade80", // green
  "#fb923c", // orange
  "#c084fc", // purple
  "#34d399", // emerald
  "#f472b6", // pink
];

function getRouteColor(index: number, selectedIndex: number): string {
  if (index === selectedIndex) return ROUTE_COLORS.selected;
  const altPos = index < selectedIndex ? index : index - 1;
  return ROUTE_ALT_PALETTE[altPos % ROUTE_ALT_PALETTE.length];
}

const OPERATOR_COLORS: Record<string, string> = {
  Jio: "#0070f3",
  Airtel: "#e53e3e",
  Vi: "#d69e2e",
  BSNL: "#38a169",
};

// ---------------------------------------------------------------------------
// Types (re-export for MapContainer)
// ---------------------------------------------------------------------------
export type HeatmapFilterType = "signal" | "weather" | "traffic" | "road";

type Props = {
  routes: RouteOption[];
  selectedRouteIndex: number;
  heatmapZones: { name: string; lat: number; lng: number; score: number; signal_strength: string; color: string }[];
  towerMarkers?: TowerMarker[];
  onRouteClick?: (index: number) => void;
  trackingPosition?: Coordinate | null;
  userLocation?: Coordinate | null;
  heatmapFilter?: HeatmapFilterType;
  onPinDrag?: (type: "source" | "destination", lat: number, lng: number) => void;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function pathToGeoJSON(path: Coordinate[]): GeoJSON.Feature<GeoJSON.LineString> {
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: path.map((p) => [p.lng, p.lat]),
    },
  };
}

function getBounds(coords: Coordinate[]): mapboxgl.LngLatBoundsLike {
  let minLng = Infinity,
    maxLng = -Infinity,
    minLat = Infinity,
    maxLat = -Infinity;
  for (const c of coords) {
    if (c.lng < minLng) minLng = c.lng;
    if (c.lng > maxLng) maxLng = c.lng;
    if (c.lat < minLat) minLat = c.lat;
    if (c.lat > maxLat) maxLat = c.lat;
  }
  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}

function createPinElement(type: "source" | "destination"): HTMLDivElement {
  const color = type === "source" ? "#3b82f6" : "#ef4444";
  const label = type === "source" ? "A" : "B";
  const el = document.createElement("div");
  el.style.cursor = "grab";
  el.innerHTML = `
    <svg width="36" height="48" viewBox="0 0 36 48">
      <defs>
        <filter id="ps-${type}" x="-20%" y="-10%" width="140%" height="130%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.3"/>
        </filter>
      </defs>
      <path d="M18 0C8.06 0 0 8.06 0 18c0 12.6 18 30 18 30s18-17.4 18-30C36 8.06 27.94 0 18 0z"
            fill="${color}" filter="url(#ps-${type})"/>
      <circle cx="18" cy="18" r="10" fill="white"/>
      <text x="18" y="23" text-anchor="middle" font-size="14" font-weight="bold" fill="${color}">${label}</text>
    </svg>`;
  return el;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function MapView({
  routes,
  selectedRouteIndex,
  towerMarkers,
  onRouteClick,
  trackingPosition,
  userLocation,
  onPinDrag,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const pinMarkersRef = useRef<mapboxgl.Marker[]>([]);
  const towerMarkersRef = useRef<mapboxgl.Marker[]>([]);
  const trackingMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const userLocMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const popupRef = useRef<mapboxgl.Popup | null>(null);
  const routeIdsRef = useRef<string[]>([]);
  const [mapLoaded, setMapLoaded] = useState(false);

  const handlePinDragEnd = useCallback(
    (type: "source" | "destination", marker: mapboxgl.Marker) => {
      const lngLat = marker.getLngLat();
      onPinDrag?.(type, lngLat.lat, lngLat.lng);
    },
    [onPinDrag],
  );

  // -----------------------------------------------------------------------
  // 1. Initialize Mapbox map
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapboxgl.accessToken = MAPBOX_TOKEN;

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: BANGALORE_CENTER,
      zoom: DEFAULT_ZOOM,
      pitch: 0,
      bearing: 0,
      antialias: true,
      attributionControl: false,
    });

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new mapboxgl.AttributionControl({ compact: true }), "bottom-right");

    map.on("load", () => setMapLoaded(true));

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      setMapLoaded(false);
    };
  }, []);

  // -----------------------------------------------------------------------
  // 2. Draw routes: layered (glow -> casing -> main) for selected,
  //    dashed for alternatives
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;
    const map = mapRef.current;

    // Clean up old sources + layers
    for (const id of routeIdsRef.current) {
      for (const suffix of ["-glow", "-casing", "-main"]) {
        const layerId = `${id}${suffix}`;
        if (map.getLayer(layerId)) map.removeLayer(layerId);
      }
      if (map.getSource(id)) map.removeSource(id);
    }
    routeIdsRef.current = [];

    // Clean up old pin markers
    pinMarkersRef.current.forEach((m) => m.remove());
    pinMarkersRef.current = [];

    if (routes.length === 0) return;

    // Draw alternatives first (behind), selected last (on top)
    const order = routes
      .map((_, i) => i)
      .sort((a, b) => {
        if (a === selectedRouteIndex) return 1;
        if (b === selectedRouteIndex) return -1;
        return 0;
      });

    for (const i of order) {
      const route = routes[i];
      if (!route.path || route.path.length < 2) continue;

      const isSelected = i === selectedRouteIndex;
      const color = getRouteColor(i, selectedRouteIndex);
      const srcId = `route-${i}`;

      map.addSource(srcId, {
        type: "geojson",
        data: pathToGeoJSON(route.path),
      });
      routeIdsRef.current.push(srcId);

      if (isSelected) {
        // Glow layer
        map.addLayer({
          id: `${srcId}-glow`,
          type: "line",
          source: srcId,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": color,
            "line-width": 18,
            "line-opacity": 0.12,
            "line-blur": 10,
          },
        });
        // Casing layer (dark outline)
        map.addLayer({
          id: `${srcId}-casing`,
          type: "line",
          source: srcId,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#1e3a5f",
            "line-width": 9,
            "line-opacity": 0.35,
          },
        });
        // Main route
        map.addLayer({
          id: `${srcId}-main`,
          type: "line",
          source: srcId,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": color,
            "line-width": 5,
            "line-opacity": 1,
          },
        });
      } else {
        // Alt: casing (subtle)
        map.addLayer({
          id: `${srcId}-casing`,
          type: "line",
          source: srcId,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": color,
            "line-width": 5,
            "line-opacity": 0.2,
            "line-dasharray": [2, 2],
          },
        });
        // Alt: main
        map.addLayer({
          id: `${srcId}-main`,
          type: "line",
          source: srcId,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": color,
            "line-width": 3,
            "line-opacity": 0.5,
            "line-dasharray": [4, 3],
          },
        });
      }

      // Click to select route
      const mainLayerId = `${srcId}-main`;
      map.on("click", mainLayerId, () => onRouteClick?.(i));

      // Cursor pointer on hover
      map.on("mouseenter", mainLayerId, () => {
        map.getCanvas().style.cursor = "pointer";
        if (!isSelected) {
          map.setPaintProperty(mainLayerId, "line-opacity", 0.8);
          map.setPaintProperty(mainLayerId, "line-width", 4);
        }
      });
      map.on("mouseleave", mainLayerId, () => {
        map.getCanvas().style.cursor = "";
        if (!isSelected) {
          map.setPaintProperty(mainLayerId, "line-opacity", 0.5);
          map.setPaintProperty(mainLayerId, "line-width", 3);
        }
        if (popupRef.current) {
          popupRef.current.remove();
          popupRef.current = null;
        }
      });

      // Hover popup for alternatives
      if (!isSelected) {
        map.on("mouseenter", mainLayerId, (e) => {
          const sLabel =
            route.signal_score >= 70 ? "Strong" : route.signal_score >= 40 ? "Medium" : "Weak";
          const sColor =
            route.signal_score >= 70 ? "#22c55e" : route.signal_score >= 40 ? "#eab308" : "#ef4444";
          if (popupRef.current) popupRef.current.remove();
          popupRef.current = new mapboxgl.Popup({ closeButton: false, offset: 14 })
            .setLngLat(e.lngLat)
            .setHTML(
              `<div style="font-family:system-ui;min-width:140px;padding:2px 0;">
                <div style="font-weight:700;font-size:13px;margin-bottom:3px;">${route.name}</div>
                <div style="display:flex;gap:10px;font-size:11px;color:#6b7280;">
                  <span>${route.eta} min</span><span>${route.distance} km</span>
                </div>
                <div style="margin-top:3px;font-size:11px;">
                  Signal: <span style="font-weight:600;color:${sColor}">${sLabel} (${Math.round(route.signal_score)})</span>
                </div>
              </div>`,
            )
            .addTo(map);
        });
      }
    }

    // Source (A) and destination (B) pins
    const selected = routes[selectedRouteIndex];
    if (selected?.path.length > 0) {
      const startPt = selected.path[0];
      const endPt = selected.path[selected.path.length - 1];

      const srcPin = new mapboxgl.Marker({
        element: createPinElement("source"),
        draggable: true,
        anchor: "bottom",
      })
        .setLngLat([startPt.lng, startPt.lat])
        .addTo(map);
      srcPin.on("dragend", () => handlePinDragEnd("source", srcPin));
      pinMarkersRef.current.push(srcPin);

      const dstPin = new mapboxgl.Marker({
        element: createPinElement("destination"),
        draggable: true,
        anchor: "bottom",
      })
        .setLngLat([endPt.lng, endPt.lat])
        .addTo(map);
      dstPin.on("dragend", () => handlePinDragEnd("destination", dstPin));
      pinMarkersRef.current.push(dstPin);

      // Fit bounds with smooth camera transition
      map.fitBounds(getBounds(selected.path), {
        padding: { top: 80, bottom: 80, left: 400, right: 80 },
        duration: 800,
      });
    }
  }, [mapLoaded, routes, selectedRouteIndex, onRouteClick, handlePinDragEnd]);

  // -----------------------------------------------------------------------
  // 3. Tower dot markers
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;
    const map = mapRef.current;

    towerMarkersRef.current.forEach((m) => m.remove());
    towerMarkersRef.current = [];

    if (!towerMarkers || towerMarkers.length === 0) return;

    for (const tower of towerMarkers) {
      const color = OPERATOR_COLORS[tower.operator] ?? "#6b7280";
      const size = tower.signal_score >= 70 ? 8 : tower.signal_score >= 40 ? 7 : 6;
      const opacity = tower.signal_score >= 70 ? 0.9 : tower.signal_score >= 40 ? 0.75 : 0.6;

      const el = document.createElement("div");
      el.style.cssText = `width:${size}px;height:${size}px;background:${color};border:1.5px solid rgba(255,255,255,0.8);border-radius:50%;opacity:${opacity};box-shadow:0 1px 3px rgba(0,0,0,.25);`;

      const sLabel =
        tower.signal_score >= 70 ? "Strong" : tower.signal_score >= 40 ? "Medium" : "Weak";
      const popup = new mapboxgl.Popup({ offset: 8, closeButton: false }).setHTML(
        `<b>${tower.operator}</b>${tower.zone ? ` -- ${tower.zone}` : ""}<br/>Signal: ${sLabel} (${Math.round(tower.signal_score)})<br/><span style="font-size:10px;color:#9ca3af;">${tower.tower_id}</span>`,
      );

      const m = new mapboxgl.Marker({ element: el })
        .setLngLat([tower.lng, tower.lat])
        .setPopup(popup)
        .addTo(map);
      towerMarkersRef.current.push(m);
    }
  }, [mapLoaded, towerMarkers]);

  // -----------------------------------------------------------------------
  // 4. Live tracking marker (pulsing blue dot)
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    if (!trackingPosition) {
      trackingMarkerRef.current?.remove();
      trackingMarkerRef.current = null;
      return;
    }

    if (!trackingMarkerRef.current) {
      const el = document.createElement("div");
      el.innerHTML = `
        <div style="position:relative;width:22px;height:22px;">
          <div style="position:absolute;inset:0;background:rgba(59,130,246,0.2);border-radius:50%;animation:mbx-pulse 2s ease-in-out infinite;"></div>
          <div style="position:absolute;top:4px;left:4px;width:14px;height:14px;background:#3b82f6;border:2.5px solid #fff;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,.4);"></div>
        </div>`;
      trackingMarkerRef.current = new mapboxgl.Marker({ element: el })
        .setLngLat([trackingPosition.lng, trackingPosition.lat])
        .addTo(mapRef.current);
    } else {
      trackingMarkerRef.current.setLngLat([trackingPosition.lng, trackingPosition.lat]);
    }
  }, [mapLoaded, trackingPosition]);

  // -----------------------------------------------------------------------
  // 5. User real-location marker
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    if (!userLocation) {
      userLocMarkerRef.current?.remove();
      userLocMarkerRef.current = null;
      return;
    }

    if (!userLocMarkerRef.current) {
      const el = document.createElement("div");
      el.innerHTML = `
        <div style="width:14px;height:14px;background:#3b82f6;border:3px solid #fff;border-radius:50%;box-shadow:0 0 0 2px rgba(59,130,244,.3),0 1px 4px rgba(0,0,0,.3);"></div>`;
      userLocMarkerRef.current = new mapboxgl.Marker({ element: el })
        .setLngLat([userLocation.lng, userLocation.lat])
        .addTo(mapRef.current);
    } else {
      userLocMarkerRef.current.setLngLat([userLocation.lng, userLocation.lat]);
    }
  }, [mapLoaded, userLocation]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <>
      {!mapLoaded && (
        <div className="absolute inset-0 z-10 bg-gray-50 flex flex-col items-center justify-center gap-4">
          <div className="w-10 h-10 border-3 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
          <p className="text-sm text-gray-400">Loading map...</p>
        </div>
      )}
      <div
        id="map-area"
        ref={containerRef}
        style={{ position: "absolute", inset: 0, zIndex: 0, width: "100%", height: "100%" }}
      />
    </>
  );
}
