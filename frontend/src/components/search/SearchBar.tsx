"use client";

import { Loader2, MapPin, Search, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { geocodeService, type GeocodeSuggestion } from "@/src/services/api";

type Props = {
  source: string;
  destination: string;
  onSourceChange: (v: string) => void;
  onDestinationChange: (v: string) => void;
  onSourceCoords?: (lat: number | null, lon: number | null) => void;
  onDestCoords?: (lat: number | null, lon: number | null) => void;
  onSearch: () => void;
  onUseMyLocation?: () => void;
  geoLoading?: boolean;
};

/** Shorten a Nominatim display_name to the first 2 comma parts. */
function shortenName(displayName: string): string {
  return displayName.split(",").slice(0, 2).join(",").trim();
}

/** Highlight matching text in a string */
function highlightMatch(text: string, query: string) {
  if (!query || query.length < 1) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span className="font-bold text-blue-600">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

export function SearchBar({
  source,
  destination,
  onSourceChange,
  onDestinationChange,
  onSourceCoords,
  onDestCoords,
  onSearch,
  onUseMyLocation,
  geoLoading,
}: Props) {
  const [focusedField, setFocusedField] = useState<"source" | "dest" | null>(null);
  const [geoResults, setGeoResults] = useState<GeocodeSuggestion[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentValue = focusedField === "source" ? source : destination;

  // Debounced geocode search triggered on every keystroke (>= 1 char)
  const triggerGeocode = useCallback((query: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim().length < 1) {
      setGeoResults([]);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    // Short debounce (150ms) so suggestions feel instant
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await geocodeService.search(query);
        setGeoResults(results);
      } catch {
        // keep stale results on error
      }
      setIsSearching(false);
    }, 150);
  }, []);

  // Called on every keystroke in either input
  const handleInput = useCallback(
    (value: string, field: "source" | "dest") => {
      if (field === "source") {
        onSourceChange(value);
        onSourceCoords?.(null, null); // clear geocoded coords when typing manually
      } else {
        onDestinationChange(value);
        onDestCoords?.(null, null);
      }
      triggerGeocode(value);
    },
    [onSourceChange, onDestinationChange, onSourceCoords, onDestCoords, triggerGeocode],
  );

  // Select a geocoded result — passes lat/lon to parent for @lat,lng routing
  const handleGeoSelect = useCallback(
    (sug: GeocodeSuggestion) => {
      const label = shortenName(sug.city);
      if (focusedField === "source") {
        onSourceChange(label);
        onSourceCoords?.(sug.lat, sug.lon);
      } else {
        onDestinationChange(label);
        onDestCoords?.(sug.lat, sug.lon);
      }
      setGeoResults([]);
      setFocusedField(null);
      const other = focusedField === "source" ? destination : source;
      if (other) setTimeout(onSearch, 100);
    },
    [
      focusedField, source, destination,
      onSourceChange, onDestinationChange,
      onSourceCoords, onDestCoords, onSearch,
    ],
  );

  const showLocationOption = focusedField === "source" && !source && onUseMyLocation;
  const hasDropdown =
    focusedField !== null &&
    (showLocationOption || isSearching || geoResults.length > 0 || currentValue.trim().length >= 1);

  return (
    <div id="search-bar" ref={containerRef} className="absolute top-4 left-4 z-[1100] w-[340px]">
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        {/* Source input */}
        <div className="flex items-center px-4 py-3 gap-3 border-b border-gray-100">
          <div className="w-3 h-3 rounded-full bg-blue-500 ring-2 ring-blue-200 shrink-0" />
          <input
            type="text"
            placeholder="Enter start location"
            value={source}
            onChange={(e) => handleInput(e.target.value, "source")}
            onFocus={() => { setFocusedField("source"); triggerGeocode(source); }}
            onBlur={() => setTimeout(() => {
              if (!containerRef.current?.contains(document.activeElement)) {
                setFocusedField(null);
              }
            }, 50)}
            onKeyDown={(e) => { if (e.key === "Enter" && source && destination) onSearch(); }}
            className="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-transparent"
          />
          {source && (
            <button
              type="button"
              onClick={() => { onSourceChange(""); onSourceCoords?.(null, null); }}
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
            onChange={(e) => handleInput(e.target.value, "dest")}
            onFocus={() => { setFocusedField("dest"); triggerGeocode(destination); }}
            onBlur={() => setTimeout(() => {
              if (!containerRef.current?.contains(document.activeElement)) {
                setFocusedField(null);
              }
            }, 50)}
            onKeyDown={(e) => { if (e.key === "Enter" && source && destination) onSearch(); }}
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
      {hasDropdown && (
        <div className="mt-1 bg-white rounded-xl shadow-lg max-h-64 overflow-y-auto">
          {/* Use my location (source only) */}
          {showLocationOption && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onUseMyLocation?.(); setFocusedField(null); }}
              className="w-full text-left px-4 py-3 text-sm text-blue-600 hover:bg-blue-50 flex items-center gap-3 cursor-pointer border-b border-gray-100"
            >
              <MapPin size={16} className="text-blue-500 shrink-0" />
              {geoLoading ? "Getting your location..." : "Your location"}
            </button>
          )}

          {/* Live geocode searching indicator */}
          {isSearching && (
            <div className="px-4 py-3 text-sm text-gray-400 flex items-center gap-2">
              <Loader2 size={14} className="animate-spin shrink-0" />
              Searching locations...
            </div>
          )}

          {/* Live geocoded results */}
          {geoResults.map((sug, i) => (
            <button
              key={`geo-${i}`}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => handleGeoSelect(sug)}
              className="w-full text-left px-4 py-2.5 hover:bg-blue-50 flex items-start gap-3 cursor-pointer border-b border-gray-50"
            >
              <MapPin size={14} className="text-blue-400 mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-gray-800 truncate">
                  {highlightMatch(shortenName(sug.city), currentValue)}
                </p>
                <p className="text-xs text-gray-400 truncate">{sug.city}</p>
              </div>
            </button>
          ))}

          {/* No results state */}
          {!isSearching && geoResults.length === 0 && currentValue.trim().length >= 2 && (
            <div className="px-4 py-3 text-sm text-gray-400">
              No results found for &quot;{currentValue}&quot;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
