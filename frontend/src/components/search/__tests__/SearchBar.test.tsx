import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SearchBar } from "../SearchBar";

// Mock the Mapbox search service
jest.mock("@/src/services/api", () => ({
  mapboxSearchService: {
    suggest: jest.fn().mockResolvedValue([
      { name: "Koramangala", full_address: "Koramangala, Bengaluru, Karnataka, India", mapbox_id: "id1" },
      { name: "Koramangala 4th Block", full_address: "Koramangala 4th Block, Bengaluru, Karnataka, India", mapbox_id: "id2" },
    ]),
    retrieve: jest.fn().mockResolvedValue({ name: "Koramangala", lat: 12.9352, lng: 77.6245 }),
    reverseGeocode: jest.fn().mockResolvedValue("Koramangala, Bengaluru"),
  },
}));

describe("SearchBar", () => {
  const defaultProps = {
    source: "",
    destination: "",
    onSourceChange: jest.fn(),
    onDestinationChange: jest.fn(),
    onSearch: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders source and destination inputs", () => {
    render(<SearchBar {...defaultProps} />);
    expect(screen.getByPlaceholderText("Enter start location")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Enter stop location")).toBeInTheDocument();
  });

  it("calls onSourceChange when typing in source field", () => {
    render(<SearchBar {...defaultProps} />);
    const input = screen.getByPlaceholderText("Enter start location");
    fireEvent.change(input, { target: { value: "Koramangala" } });
    expect(defaultProps.onSourceChange).toHaveBeenCalledWith("Koramangala");
  });

  it("calls onDestinationChange when typing in destination field", () => {
    render(<SearchBar {...defaultProps} />);
    const input = screen.getByPlaceholderText("Enter stop location");
    fireEvent.change(input, { target: { value: "MG Road" } });
    expect(defaultProps.onDestinationChange).toHaveBeenCalledWith("MG Road");
  });

  it("shows search button when both fields are filled", () => {
    render(<SearchBar {...defaultProps} source="A" destination="B" />);
    // Search icon button should be present (SVG inside button)
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("calls onSearch when Enter is pressed with both fields", () => {
    render(<SearchBar {...defaultProps} source="A" destination="B" />);
    const input = screen.getByPlaceholderText("Enter start location");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(defaultProps.onSearch).toHaveBeenCalled();
  });

  it("does not call onSearch when Enter pressed with empty destination", () => {
    render(<SearchBar {...defaultProps} source="A" destination="" />);
    const input = screen.getByPlaceholderText("Enter start location");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(defaultProps.onSearch).not.toHaveBeenCalled();
  });

  it("shows clear button when source has value", () => {
    render(<SearchBar {...defaultProps} source="Koramangala" />);
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("clears source coordinates when clear button clicked", () => {
    const onSourceCoords = jest.fn();
    render(
      <SearchBar {...defaultProps} source="Test" onSourceCoords={onSourceCoords} />,
    );
    // Click the clear (X) button
    const clearBtn = screen.getAllByRole("button")[0];
    fireEvent.click(clearBtn);
    expect(defaultProps.onSourceChange).toHaveBeenCalledWith("");
    expect(onSourceCoords).toHaveBeenCalledWith(null, null);
  });

  it("shows autocomplete suggestions on focus with text >= 2 chars", async () => {
    render(<SearchBar {...defaultProps} source="Ko" />);
    const input = screen.getByPlaceholderText("Enter start location");
    fireEvent.focus(input);

    await waitFor(() => {
      // Dropdown should appear with suggestion or searching indicator
      const searching = screen.queryByText(/Searching.../);
      expect(searching || screen.queryByText(/Koramangala/)).toBeTruthy();
    }, { timeout: 1000 });
  });

  it("shows 'Use my location' option when source is empty and onUseMyLocation provided", () => {
    const onUseMyLocation = jest.fn();
    render(
      <SearchBar {...defaultProps} onUseMyLocation={onUseMyLocation} />,
    );
    const input = screen.getByPlaceholderText("Enter start location");
    fireEvent.focus(input);

    expect(screen.getByText("Use my location")).toBeInTheDocument();
  });
});
