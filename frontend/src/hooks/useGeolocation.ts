"use client";

import { useCallback, useEffect, useState } from "react";
import type { Coordinate } from "@/src/types/route";

type GeoState = {
  location: Coordinate | null;
  error: string | null;
  loading: boolean;
  granted: boolean;
};

export function useGeolocation() {
  const [state, setState] = useState<GeoState>({
    location: null,
    error: null,
    loading: false,
    granted: false,
  });

  const request = useCallback(() => {
    if (!navigator.geolocation) {
      setState((s) => ({ ...s, error: "Geolocation not supported" }));
      return;
    }

    setState((s) => ({ ...s, loading: true, error: null }));

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setState({
          location: { lat: pos.coords.latitude, lng: pos.coords.longitude },
          error: null,
          loading: false,
          granted: true,
        });
      },
      (err) => {
        setState((s) => ({
          ...s,
          loading: false,
          error:
            err.code === 1
              ? "Location access denied"
              : err.code === 2
                ? "Location unavailable"
                : "Location request timed out",
        }));
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }, []);

  // Watch for continuous updates once granted
  useEffect(() => {
    if (!state.granted || !navigator.geolocation) return;

    const id = navigator.geolocation.watchPosition(
      (pos) => {
        setState((s) => ({
          ...s,
          location: { lat: pos.coords.latitude, lng: pos.coords.longitude },
        }));
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 5000 },
    );

    return () => navigator.geolocation.clearWatch(id);
  }, [state.granted]);

  return { ...state, request };
}
