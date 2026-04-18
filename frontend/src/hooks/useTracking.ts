"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Coordinate } from "@/src/types/route";

export function useTracking(path: Coordinate[], active: boolean) {
  const [position, setPosition] = useState<Coordinate | null>(null);
  const indexRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  /** Fraction of path completed (0..1) */
  const [progress, setProgress] = useState(0);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    indexRef.current = 0;
    setPosition(null);
    setProgress(0);
  }, []);

  useEffect(() => {
    if (!active || path.length === 0) {
      stop();
      return;
    }

    indexRef.current = 0;
    setPosition(path[0]);
    setProgress(0);

    intervalRef.current = setInterval(() => {
      indexRef.current += 1;
      if (indexRef.current >= path.length) {
        indexRef.current = 0;
      }
      setPosition(path[indexRef.current]);
      setProgress(path.length > 1 ? indexRef.current / (path.length - 1) : 0);
    }, 800);

    return stop;
  }, [active, path, stop]);

  return { position, progress, stop };
}
