"use client";

import { Loader2, MapPin, Search, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { mapboxSearchService, type MapboxSuggestion } from "@/src/services/api";

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

/** Highlight the matching portion of `text` for the current `query`. */
function highlightMatch(text: string, query: string) {
  if (!query) return text;
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
  const [suggestions, setSuggestions] = useState<MapboxSuggestion[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isRetrieving, setIsRetrieving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentValue = focusedField === "source" ? source : destination;

  // -----------------------------------------------------------------------
  // Fetch autocomplete suggestions from Mapbox Search Box
  // -----------------------------------------------------------------------
  const fetchSuggestions = useCallback(async (query: string) => {
    setIsSearching(true);
    try {
      const results = await mapboxSearchService.suggest(query);
      setSuggestions(results);
    } catch {
      // keep stale suggestions on transient errors
    }
    setIsSearching(false);
  }, []);

  // Debounced trigger: fire 300ms after the user stops typing
  const triggerSuggest = useCallback(
    (query: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (query.trim().length < 2) {
        setSuggestions([]);
        setIsSearching(false);
        return;
      }
      debounceRef.current = setTimeout(() => fetchSuggestions(query), 300);
    },
    [fetchSuggestions],
  );

  // Called on every keystroke
  const handleInput = useCallback(
    (value: string, field: "source" | "dest") => {
      if (field === "source") {
        onSourceChange(value);
        onSourceCoords?.(null, null); // clear resolved coords while typing
      } else {
        onDestinationChange(value);
        onDestCoords?.(null, null);
      }
      triggerSuggest(value);
    },
    [onSourceChange, onDestinationChange, onSourceCoords, onDestCoords, triggerSuggest],
  );

  // -----------------------------------------------------------------------
  // Step 2: retrieve exact coordinates when user picks a suggestion
  // -----------------------------------------------------------------------
  const handleSelect = useCallback(
    async (sug: MapboxSuggestion) => {
      // Immediately show the chosen name so the field doesn't flicker
      const label = sug.name;
      if (focusedField === "source") {
        onSourceChange(label);
      } else {
        onDestinationChange(label);
      }
      setSuggestions([]);
      setFocusedField(null);

      setIsRetrieving(true);
      const result = await mapboxSearchService.retrieve(sug.mapbox_id);
      setIsRetrieving(false);

      if (result) {
        // Update label to the canonical name returned by retrieve
        if (focusedField === "source") {
          onSourceChange(result.name || label);
          onSourceCoords?.(result.lat, result.lng);
        } else {
          onDestinationChange(result.name || label);
          onDestCoords?.(result.lat, result.lng);
        }
        // Auto-search when both fields are filled
        const other = focusedField === "source" ? destination : source;
        if (other) setTimeout(onSearch, 100);
      }
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
    (showLocationOption || isSearching || suggestions.length > 0 || currentValue.trim().length >= 2);

  return (
    <div id="search-bar" ref={containerRef} className="absolute top-4 left-4 z-[1100] w-[340px]">
      <div className={`bg-white rounded-xl shadow-lg overflow-hidden ${isRetrieving ? "opacity-80" : ""}`}>
        {/* Source input */}
        <div className="flex items-center px-4 py-3 gap-3 border-b border-gray-100">
          <div className="w-3 h-3 rounded-full bg-blue-500 ring-2 ring-blue-200 shrink-0" />
          <input
            type="text"
            placeholder="Enter start location"
            value={source}
            onChange={(e) => handleInput(e.target.value, "source")}
            onFocus={() => { setFocusedField("source"); triggerSuggest(source); }}
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
              onClick={() => { onSourceChange(""); onSourceCoords?.(null, null); setSuggestions([]); }}
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
            onFocus={() => { setFocusedField("dest"); triggerSuggest(destination); }}
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

      {/* Autocomplete dropdown */}
      {hasDropdown && (
        <div className="mt-1 bg-white rounded-xl shadow-lg max-h-72 overflow-y-auto">
          {/* Use my location (source only) */}
          {showLocationOption && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onUseMyLocation?.(); setFocusedField(null); }}
              className="w-full text-left px-4 py-3 text-sm text-blue-600 hover:bg-blue-50 flex items-center gap-3 cursor-pointer border-b border-gray-100"
            >
              <MapPin size={16} className="text-blue-500 shrink-0" />
              {geoLoading ? "Getting your location..." : "Use my location"}
            </button>
          )}

          {/* Searching indicator */}
          {isSearching && (
            <div className="px-4 py-3 text-sm text-gray-400 flex items-center gap-2">
              <Loader2 size={14} className="animate-spin shrink-0" />
              Searching...
            </div>
          )}

          {/* Mapbox autocomplete results */}
          {suggestions.map((sug, i) => (
            <button
              key={`${sug.mapbox_id}-${i}`}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => handleSelect(sug)}
              className="w-full text-left px-4 py-2.5 hover:bg-blue-50 flex items-start gap-3 cursor-pointer border-b border-gray-50 last:border-0"
            >
              <MapPin size={14} className="text-blue-400 mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-gray-800 truncate">
                  {highlightMatch(sug.name, currentValue)}
                </p>
                <p className="text-xs text-gray-400 truncate">{sug.full_address}</p>
              </div>
            </button>
          ))}

          {/* No results */}
          {!isSearching && suggestions.length === 0 && currentValue.trim().length >= 2 && (
            <div className="px-4 py-3 text-sm text-gray-400">
              No results found for &quot;{currentValue}&quot;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
