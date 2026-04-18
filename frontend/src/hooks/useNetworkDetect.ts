"use client";

import { useEffect, useState } from "react";
import type { TelecomMode } from "@/src/types/route";

type NetworkInfo = {
  type: "wifi" | "cellular" | "unknown";
  effectiveType: string;
  detectedProvider: TelecomMode;
  downlink: number | null;
};

export function useNetworkDetect() {
  const [info, setInfo] = useState<NetworkInfo>({
    type: "unknown",
    effectiveType: "",
    detectedProvider: "all",
    downlink: null,
  });

  useEffect(() => {
    const nav = navigator as NavigatorWithConnection;
    const conn = nav.connection || nav.mozConnection || nav.webkitConnection;

    if (!conn) return;

    function update() {
      const c = conn!;
      const connType = (c.type ?? "unknown") as string;
      const isWifi = connType === "wifi";
      const eff = (c.effectiveType ?? "") as string;
      const dl = c.downlink ?? null;

      setInfo({
        type: isWifi ? "wifi" : connType === "cellular" ? "cellular" : "unknown",
        effectiveType: eff,
        detectedProvider: "all",
        downlink: dl,
      });
    }

    update();
    conn.addEventListener("change", update);
    return () => conn.removeEventListener("change", update);
  }, []);

  return info;
}

type NetworkConnection = {
  type?: string;
  effectiveType?: string;
  downlink?: number;
  addEventListener: (event: string, fn: () => void) => void;
  removeEventListener: (event: string, fn: () => void) => void;
};

type NavigatorWithConnection = Navigator & {
  connection?: NetworkConnection;
  mozConnection?: NetworkConnection;
  webkitConnection?: NetworkConnection;
};
