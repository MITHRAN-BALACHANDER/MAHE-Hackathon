"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Coordinate } from "@/src/types/route";

/**
 * Tracks the user's real GPS position via navigator.geolocation.watchPosition.
 * Progress is estimated as the fraction of the route path closest to the
 * current GPS position.
 */
export function useTracking(path: Coordinate[], active: boolean) {
  const [position, setPosition] = useState<Coordinate | null>(null);
  const [progress, setProgress] = useState(0);
  const watchIdRef = useRef<number | null>(null);

  /** Find the closest path index to a given GPS coordinate. */
  const closestIndex = useCallback(
    (lat: number, lng: number): number => {
      if (path.length === 0) return 0;
      let best = 0;
      let bestDist = Infinity;
      for (let i = 0; i < path.length; i++) {
        const dlat = path[i].lat - lat;
        const dlng = path[i].lng - lng;
        const d = dlat * dlat + dlng * dlng;
        if (d < bestDist) {
          bestDist = d;
          best = i;
        }
      }
      return best;
    },
    [path],
  );

  const stop = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setPosition(null);
    setProgress(0);
  }, []);

  useEffect(() => {
    if (!active || path.length === 0) {
      stop();
      return;
    }

    if (!navigator.geolocation) {
      // Fallback: no geolocation support -- stay at start
      setPosition(path[0]);
      setProgress(0);
      return;
    }

    // Start watching real GPS
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const coord: Coordinate = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };
        setPosition(coord);
        const idx = closestIndex(coord.lat, coord.lng);
        setProgress(path.length > 1 ? idx / (path.length - 1) : 0);
      },
      () => {
        // On error, keep last known position
      },
      {
        enableHighAccuracy: true,
        maximumAge: 3000,
        timeout: 10000,
      },
    );

    return stop;
  }, [active, path, stop, closestIndex]);

  return { position, progress, stop };
}
