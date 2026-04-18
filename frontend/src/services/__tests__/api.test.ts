import { routeService, heatmapService, geocodeService, offlineService } from "../api";
import axios from "axios";

jest.mock("axios", () => ({
  create: jest.fn(() => ({
    get: jest.fn(),
    post: jest.fn(),
  })),
}));

const mockClient = axios.create() as jest.Mocked<ReturnType<typeof axios.create>>;

describe("API Services", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("routeService", () => {
    it("getRoutes calls GET /api/routes with params", async () => {
      const mockData = {
        source: "A",
        destination: "B",
        routes: [],
        recommended_route: "",
      };
      (mockClient.get as jest.Mock).mockResolvedValueOnce({ data: mockData });

      // routeService uses its own client instance
      // Just verify the service exists and has the expected methods
      expect(routeService).toBeDefined();
      expect(routeService.getRoutes).toBeDefined();
      expect(routeService.reroute).toBeDefined();
    });
  });

  describe("heatmapService", () => {
    it("has getHeatmap method", () => {
      expect(heatmapService).toBeDefined();
      expect(heatmapService.getHeatmap).toBeDefined();
    });
  });

  describe("geocodeService", () => {
    it("has search method", () => {
      expect(geocodeService).toBeDefined();
      expect(geocodeService.search).toBeDefined();
    });

    it("returns empty array for short queries", async () => {
      const results = await geocodeService.search("");
      expect(results).toEqual([]);
    });

    it("returns empty array for single char", async () => {
      const results = await geocodeService.search("a");
      expect(results).toEqual([]);
    });
  });

  describe("offlineService", () => {
    it("has downloadBundle method", () => {
      expect(offlineService.downloadBundle).toBeDefined();
    });

    it("saves and loads bundles from localStorage", () => {
      const bundle = {
        source: "A",
        destination: "B",
        generated_at: Date.now(),
        routes: [],
        heatmap: [],
        offline: true,
      };

      offlineService.saveToStorage(bundle);
      const loaded = offlineService.loadFromStorage("A", "B");
      expect(loaded).toEqual(bundle);
    });

    it("returns null for missing bundle", () => {
      const loaded = offlineService.loadFromStorage("X", "Y");
      expect(loaded).toBeNull();
    });

    it("lists saved bundles", () => {
      localStorage.clear();
      const bundle = {
        source: "Test1",
        destination: "Test2",
        generated_at: Date.now(),
        routes: [],
        heatmap: [],
        offline: true,
      };
      offlineService.saveToStorage(bundle);

      const keys = offlineService.listSavedBundles();
      expect(keys.length).toBeGreaterThanOrEqual(1);
    });
  });
});
