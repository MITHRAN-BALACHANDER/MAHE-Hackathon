"use client";

import { MapPin, Search, X } from "lucide-react";
import { useCallback, useState } from "react";

const LOCATIONS = [
  "Koramangala", "Indiranagar", "Whitefield",
  "Electronic City", "MG Road", "Jayanagar", "HSR Layout", "Hebbal",
  "Marathahalli", "BTM Layout", "Rajajinagar", "Silk Board", "Peenya",
  "Yelahanka", "Bannerghatta", "KR Puram", "Sarjapur Road", "Hosur Road",
  "Majestic", "JP Nagar",
];

type Props = {
  source: string;
  destination: string;
  onSourceChange: (v: string) => void;
  onDestinationChange: (v: string) => void;
  onSearch: () => void;
  onUseMyLocation?: () => void;
  geoLoading?: boolean;
};

export function SearchBar({
  source,
  destination,
  onSourceChange,
  onDestinationChange,
  onSearch,
  onUseMyLocation,
  geoLoading,
}: Props) {
  const [focusedField, setFocusedField] = useState<"source" | "dest" | null>(null);

  const currentValue = focusedField === "source" ? source : destination;
  const onChange = focusedField === "source" ? onSourceChange : onDestinationChange;

  const filtered = LOCATIONS.filter(
    (l) =>
      l.toLowerCase().includes((currentValue ?? "").toLowerCase()) &&
      l !== (focusedField === "source" ? destination : source),
  );

  const handleSelect = useCallback(
    (loc: string) => {
      onChange(loc);
      setFocusedField(null);
      // Auto-search when both fields are filled
      const otherField = focusedField === "source" ? destination : source;
      if (otherField) {
        setTimeout(() => onSearch(), 100);
      }
    },
    [onChange, focusedField, source, destination, onSearch],
  );

  // Show "Your location" option only in source field when input is empty
  const showLocationOption = focusedField === "source" && !currentValue && onUseMyLocation;

  return (
    <div className="absolute top-4 left-4 z-[1100] w-[340px]">
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        {/* Source input */}
        <div className="flex items-center px-4 py-3 gap-3 border-b border-gray-100">
          <div className="w-3 h-3 rounded-full bg-blue-500 ring-2 ring-blue-200 shrink-0" />
          <input
            type="text"
            placeholder="Enter start location"
            value={source}
            onChange={(e) => onSourceChange(e.target.value)}
            onFocus={() => setFocusedField("source")}
            onBlur={() => setTimeout(() => setFocusedField(null), 200)}
            className="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-transparent"
          />
          {source && (
            <button
              type="button"
              onClick={() => onSourceChange("")}
              className="text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Destination input */}
        <div className="flex items-center px-4 py-3 gap-3">
          <div className="w-3 h-3 rounded-full bg-red-500 ring-2 ring-red-200 shrink-0" />
          <input
            type="text"
            placeholder="Enter stop location"
            value={destination}
            onChange={(e) => onDestinationChange(e.target.value)}
            onFocus={() => setFocusedField("dest")}
            onBlur={() => setTimeout(() => setFocusedField(null), 200)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && source && destination) onSearch();
            }}
            className="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-transparent"
          />
          {source && destination && (
            <button
              type="button"
              onClick={onSearch}
              className="text-blue-500 hover:text-blue-700 cursor-pointer"
            >
              <Search size={18} />
            </button>
          )}
        </div>
      </div>

      {/* Dropdown */}
      {focusedField && (
        <div className="mt-1 bg-white rounded-xl shadow-lg max-h-56 overflow-y-auto">
          {/* Your location option */}
          {showLocationOption && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onUseMyLocation?.();
                setFocusedField(null);
              }}
              className="w-full text-left px-4 py-3 text-sm text-blue-600 hover:bg-blue-50 flex items-center gap-3 cursor-pointer border-b border-gray-100"
            >
              <MapPin size={16} className="text-blue-500 shrink-0" />
              {geoLoading ? "Getting your location..." : "Your location"}
            </button>
          )}

          {/* Location suggestions */}
          {filtered.length > 0 &&
            filtered.map((loc) => (
              <button
                key={loc}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(loc)}
                className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3 cursor-pointer"
              >
                <Search size={14} className="text-gray-400 shrink-0" />
                {loc}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
