"use client";

import { Download, Filter, MessageCircle, X } from "lucide-react";
import { useState } from "react";
import type { TelecomMode } from "@/src/types/route";
import { ChatBot } from "@/src/components/chat/ChatBot";

type Props = {
  preference: number;
  telecom: TelecomMode;
  onPreferenceChange: (v: number) => void;
  onTelecomChange: (v: TelecomMode) => void;
  onChatApply?: (source: string, destination: string, preference: number, telecom: TelecomMode) => void;
  detectedNetwork: string;
  maxEtaFactor?: number;
  onMaxEtaFactorChange?: (v: number) => void;
  onDownloadOffline?: () => void;
  offlineReady?: boolean;
};

const PRESET_FILTERS = [
  { label: "Less Traffic", pref: 20 },
  { label: "Balanced", pref: 50 },
  { label: "Best Signal", pref: 90 },
];

export function FilterPanel({
  preference,
  telecom,
  onPreferenceChange,
  onTelecomChange,
  onChatApply,
  detectedNetwork,
  maxEtaFactor = 1.5,
  onMaxEtaFactorChange,
  onDownloadOffline,
  offlineReady,
}: Props) {
  const [open, setOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="absolute top-4 right-4 z-[1000]">
      {/* Toggle buttons */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setChatOpen(!chatOpen);
            if (!chatOpen) setOpen(false);
          }}
          className="bg-white shadow-lg rounded-xl px-4 py-2.5 flex items-center gap-2 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer transition-colors"
        >
          <MessageCircle size={16} />
          Get Personalised Route
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(!open);
            if (!open) setChatOpen(false);
          }}
          className="bg-white shadow-lg rounded-xl px-4 py-2.5 flex items-center gap-2 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer transition-colors"
        >
          <Filter size={16} />
          Filters
        </button>
      </div>

      {/* Chatbot panel */}
      {chatOpen && (
        <div className="mt-2 bg-white rounded-xl shadow-xl w-80 overflow-hidden" style={{ height: 420 }}>
          <ChatBot
            onClose={() => setChatOpen(false)}
            onApply={(src, dest, pref, tel) => {
              onChatApply?.(src, dest, pref, tel);
              setChatOpen(false);
            }}
            detectedNetwork={detectedNetwork}
          />
        </div>
      )}

      {/* Filter panel */}
      {open && (
        <div className="mt-2 bg-white rounded-xl shadow-xl w-72 p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-800">Route Preferences</h3>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <X size={16} />
            </button>
          </div>

          {/* Presets */}
          <div className="flex gap-2 mb-4">
            {PRESET_FILTERS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => onPreferenceChange(p.pref)}
                className={`flex-1 text-xs py-2 rounded-lg font-medium cursor-pointer transition-colors ${
                  preference === p.pref
                    ? "bg-blue-500 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* ETA Constraint */}
          {onMaxEtaFactorChange && (
            <div className="mb-4">
              <label className="text-xs font-medium text-gray-600 mb-1 block">
                Max ETA Limit: {maxEtaFactor === 0 ? "None" : `${Math.round(maxEtaFactor * 100)}% of fastest`}
              </label>
              <input
                type="range"
                min={0}
                max={3}
                step={0.1}
                value={maxEtaFactor}
                onChange={(e) => onMaxEtaFactorChange(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
              <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                <span>No limit</span>
                <span>1.5x</span>
                <span>3x</span>
              </div>
            </div>
          )}

          {/* Detected network info */}
          {detectedNetwork && detectedNetwork !== "unknown" && (
            <div className="mb-4 px-3 py-2 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-700">
                Detected network: <span className="font-semibold">{detectedNetwork}</span>
              </p>
            </div>
          )}

          {/* Telecom */}
          <div className="mb-4">
            <label className="text-xs font-medium text-gray-600 mb-2 block">
              Network Provider
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {([
                { value: "all" as TelecomMode, label: "All Networks" },
                { value: "jio" as TelecomMode, label: "Jio" },
                { value: "airtel" as TelecomMode, label: "Airtel" },
                { value: "vi" as TelecomMode, label: "Vi" },
                { value: "multi" as TelecomMode, label: "Multi-SIM" },
              ]).map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => onTelecomChange(opt.value)}
                  className={`text-xs py-2 rounded-lg font-medium cursor-pointer transition-colors ${
                    telecom === opt.value
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Download for Offline */}
          {onDownloadOffline && (
            <button
              type="button"
              onClick={onDownloadOffline}
              className={`w-full text-xs py-2.5 rounded-lg font-medium cursor-pointer transition-colors flex items-center justify-center gap-2 ${
                offlineReady
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              <Download size={14} />
              {offlineReady ? "Offline Data Ready" : "Download for Offline"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
