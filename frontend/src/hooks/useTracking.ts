"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Coordinate } from "@/src/types/route";

export function useTracking(path: Coordinate[], active: boolean) {
  const [position, setPosition] = useState<Coordinate | null>(null);
  const indexRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    indexRef.current = 0;
    setPosition(null);
  }, []);

  useEffect(() => {
    if (!active || path.length === 0) {
      stop();
      return;
    }

    indexRef.current = 0;
    setPosition(path[0]);

    intervalRef.current = setInterval(() => {
      indexRef.current += 1;
      if (indexRef.current >= path.length) {
        indexRef.current = 0;
      }
      setPosition(path[indexRef.current]);
    }, 800);

    return stop;
  }, [active, path, stop]);

  return { position, stop };
}
