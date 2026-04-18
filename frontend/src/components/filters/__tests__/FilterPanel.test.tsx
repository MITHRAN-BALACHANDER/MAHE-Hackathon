import { render, screen, fireEvent } from "@testing-library/react";
import { FilterPanel } from "../FilterPanel";

// Mock ChatBot
jest.mock("@/src/components/chat/ChatBot", () => ({
  ChatBot: ({ onClose }: any) => (
    <div data-testid="chatbot">
      <button onClick={onClose}>Close Chat</button>
    </div>
  ),
}));

describe("FilterPanel", () => {
  const defaultProps = {
    preference: 50,
    telecom: "all" as const,
    onPreferenceChange: jest.fn(),
    onTelecomChange: jest.fn(),
    detectedNetwork: "unknown",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders filter and chat buttons", () => {
    render(<FilterPanel {...defaultProps} />);
    expect(screen.getByText("Filters")).toBeInTheDocument();
    expect(screen.getByText("Get Personalised Route")).toBeInTheDocument();
  });

  it("opens filter panel on click", () => {
    render(<FilterPanel {...defaultProps} />);
    fireEvent.click(screen.getByText("Filters"));
    expect(screen.getByText("Route Preferences")).toBeInTheDocument();
  });

  it("shows preset filter buttons", () => {
    render(<FilterPanel {...defaultProps} />);
    fireEvent.click(screen.getByText("Filters"));
    expect(screen.getByText("Less Traffic")).toBeInTheDocument();
    expect(screen.getByText("Balanced")).toBeInTheDocument();
    expect(screen.getByText("Best Signal")).toBeInTheDocument();
  });

  it("calls onPreferenceChange when preset clicked", () => {
    render(<FilterPanel {...defaultProps} />);
    fireEvent.click(screen.getByText("Filters"));
    fireEvent.click(screen.getByText("Best Signal"));
    expect(defaultProps.onPreferenceChange).toHaveBeenCalledWith(90);
  });

  it("shows telecom options", () => {
    render(<FilterPanel {...defaultProps} />);
    fireEvent.click(screen.getByText("Filters"));
    expect(screen.getByText("All Networks")).toBeInTheDocument();
    expect(screen.getByText("Jio")).toBeInTheDocument();
    expect(screen.getByText("Airtel")).toBeInTheDocument();
    expect(screen.getByText("Vi")).toBeInTheDocument();
    expect(screen.getByText("Multi-SIM")).toBeInTheDocument();
  });

  it("calls onTelecomChange when carrier clicked", () => {
    render(<FilterPanel {...defaultProps} />);
    fireEvent.click(screen.getByText("Filters"));
    fireEvent.click(screen.getByText("Jio"));
    expect(defaultProps.onTelecomChange).toHaveBeenCalledWith("jio");
  });

  it("shows heatmap layer options when handler provided", () => {
    const onHeatmapFilterChange = jest.fn();
    render(
      <FilterPanel
        {...defaultProps}
        heatmapFilter="signal"
        onHeatmapFilterChange={onHeatmapFilterChange}
      />,
    );
    fireEvent.click(screen.getByText("Filters"));
    expect(screen.getByText("Signal")).toBeInTheDocument();
    expect(screen.getByText("Weather")).toBeInTheDocument();
    expect(screen.getByText("Traffic")).toBeInTheDocument();
    expect(screen.getByText("Road Type")).toBeInTheDocument();
  });

  it("calls onHeatmapFilterChange when layer clicked", () => {
    const onHeatmapFilterChange = jest.fn();
    render(
      <FilterPanel
        {...defaultProps}
        heatmapFilter="signal"
        onHeatmapFilterChange={onHeatmapFilterChange}
      />,
    );
    fireEvent.click(screen.getByText("Filters"));
    fireEvent.click(screen.getByText("Weather"));
    expect(onHeatmapFilterChange).toHaveBeenCalledWith("weather");
  });

  it("opens chatbot panel on chat button click", () => {
    render(<FilterPanel {...defaultProps} />);
    fireEvent.click(screen.getByText("Get Personalised Route"));
    expect(screen.getByTestId("chatbot")).toBeInTheDocument();
  });

  it("shows detected network when available", () => {
    render(<FilterPanel {...defaultProps} detectedNetwork="Airtel" />);
    fireEvent.click(screen.getByText("Filters"));
    expect(screen.getAllByText(/Airtel/).length).toBeGreaterThan(0);
  });

  it("shows download offline button when handler provided", () => {
    const onDownloadOffline = jest.fn();
    render(<FilterPanel {...defaultProps} onDownloadOffline={onDownloadOffline} />);
    fireEvent.click(screen.getByText("Filters"));
    expect(screen.getByText("Download for Offline")).toBeInTheDocument();
  });

  it("closes filter panel on X button click", () => {
    render(<FilterPanel {...defaultProps} />);
    fireEvent.click(screen.getByText("Filters"));
    expect(screen.getByText("Route Preferences")).toBeInTheDocument();

    // Click the close (X) button
    const closeButtons = screen.getAllByRole("button");
    const xButton = closeButtons.find((btn) =>
      btn.querySelector("svg") && btn.classList.contains("text-gray-400"),
    );
    if (xButton) fireEvent.click(xButton);
  });
});
