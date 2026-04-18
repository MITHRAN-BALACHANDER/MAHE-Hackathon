// Mock Leaflet module for Jest testing
const L = {
  map: jest.fn(() => ({
    setView: jest.fn().mockReturnThis(),
    remove: jest.fn(),
    fitBounds: jest.fn(),
    getContainer: jest.fn(() => ({ style: {} })),
    addLayer: jest.fn(),
    removeLayer: jest.fn(),
  })),
  tileLayer: jest.fn(() => ({
    addTo: jest.fn().mockReturnThis(),
    on: jest.fn(),
  })),
  marker: jest.fn(() => ({
    addTo: jest.fn().mockReturnThis(),
    remove: jest.fn(),
    setLatLng: jest.fn(),
    bindTooltip: jest.fn().mockReturnThis(),
    on: jest.fn(),
    getLatLng: jest.fn(() => ({ lat: 12.97, lng: 77.59 })),
  })),
  polyline: jest.fn(() => ({
    addTo: jest.fn().mockReturnThis(),
    remove: jest.fn(),
    setStyle: jest.fn(),
    bindTooltip: jest.fn().mockReturnThis(),
    on: jest.fn(),
  })),
  layerGroup: jest.fn(() => ({
    addTo: jest.fn().mockReturnThis(),
    clearLayers: jest.fn(),
    addLayer: jest.fn(),
  })),
  divIcon: jest.fn(() => ({})),
  latLngBounds: jest.fn(() => ({
    extend: jest.fn(),
  })),
  control: {
    zoom: jest.fn(() => ({ addTo: jest.fn() })),
    attribution: jest.fn(() => ({ addTo: jest.fn() })),
  },
};

export default L;
export { L };
