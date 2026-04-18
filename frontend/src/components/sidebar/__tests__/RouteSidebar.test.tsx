import { render, screen, fireEvent } from "@testing-library/react";
import { RouteSidebar } from "../RouteSidebar";
import type { RouteOption } from "@/src/types/route";

const mockRoutes: RouteOption[] = [
  {
    name: "Route 1 via Hosur Road",
    eta: 35,
    distance: 18.4,
    signal_score: 72,
    weighted_score: 68,
    zones: ["Electronic City", "HSR Layout"],
    path: [
      { lat: 12.85, lng: 77.66 },
      { lat: 12.97, lng: 77.59 },
    ],
    stability_score: 78,
    continuity_score: 82,
  },
  {
    name: "Route 2 via ORR",
    eta: 42,
    distance: 24.1,
    signal_score: 85,
    weighted_score: 75,
    zones: ["Marathahalli", "Whitefield"],
    path: [
      { lat: 12.85, lng: 77.66 },
      { lat: 12.99, lng: 77.74 },
    ],
    stability_score: 90,
    rejected: false,
  },
  {
    name: "Route 3 Slow",
    eta: 65,
    distance: 30,
    signal_score: 45,
    weighted_score: 35,
    zones: ["Far Zone"],
    path: [],
    rejected: true,
  },
];

describe("RouteSidebar", () => {
  const defaultProps = {
    routes: mockRoutes,
    selectedIndex: 0,
    recommendedRoute: "Route 2 via ORR",
    onSelect: jest.fn(),
    onClose: jest.fn(),
    visible: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders route cards when visible", () => {
    render(<RouteSidebar {...defaultProps} />);
    expect(screen.getByText("Route 1 via Hosur Road")).toBeInTheDocument();
    expect(screen.getByText("Route 2 via ORR")).toBeInTheDocument();
  });

  it("shows route count", () => {
    render(<RouteSidebar {...defaultProps} />);
    expect(screen.getByText("3 options")).toBeInTheDocument();
  });

  it("shows ETA and distance for each route", () => {
    render(<RouteSidebar {...defaultProps} />);
    expect(screen.getByText("35 min")).toBeInTheDocument();
    expect(screen.getByText("18.4 km")).toBeInTheDocument();
  });

  it("shows signal badge", () => {
    render(<RouteSidebar {...defaultProps} />);
    // Route 1 signal_score=72 -> "Strong"
    expect(screen.getByText(/Strong 72/)).toBeInTheDocument();
  });

  it("marks rejected routes with 'Too Slow' badge", () => {
    render(<RouteSidebar {...defaultProps} />);
    expect(screen.getByText("Too Slow")).toBeInTheDocument();
  });

  it("calls onSelect when route clicked", () => {
    render(<RouteSidebar {...defaultProps} />);
    fireEvent.click(screen.getByText("Route 2 via ORR"));
    expect(defaultProps.onSelect).toHaveBeenCalledWith(1);
  });

  it("calls onClose when back button clicked", () => {
    render(<RouteSidebar {...defaultProps} />);
    const buttons = screen.getAllByRole("button");
    // First button is the close chevron
    fireEvent.click(buttons[0]);
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it("returns null when not visible", () => {
    const { container } = render(
      <RouteSidebar {...defaultProps} visible={false} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null when routes empty", () => {
    const { container } = render(
      <RouteSidebar {...defaultProps} routes={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("shows stability label for routes with stability score", () => {
    render(<RouteSidebar {...defaultProps} />);
    // Route 1 stability=78 -> "Stable"
    expect(screen.getAllByText(/Stable/).length).toBeGreaterThan(0);
  });

  it("shows zone tags", () => {
    render(<RouteSidebar {...defaultProps} />);
    expect(screen.getByText("Electronic City")).toBeInTheDocument();
    expect(screen.getByText("HSR Layout")).toBeInTheDocument();
  });

  it("shows suggested badge when route matches suggestedRoute", () => {
    render(
      <RouteSidebar {...defaultProps} suggestedRoute="Route 2 via ORR" />,
    );
    expect(screen.getByText("Suggested")).toBeInTheDocument();
  });
});
