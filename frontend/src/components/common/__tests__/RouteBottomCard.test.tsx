import { render, screen, fireEvent } from "@testing-library/react";
import { RouteBottomCard } from "../RouteBottomCard";
import type { RouteOption } from "@/src/types/route";

const mockRoute: RouteOption = {
  name: "Route 1 via Hosur Road",
  eta: 35,
  distance: 18.4,
  signal_score: 72,
  weighted_score: 68,
  zones: ["Electronic City", "HSR Layout", "Koramangala"],
  path: [],
};

describe("RouteBottomCard", () => {
  const defaultProps = {
    route: mockRoute,
    eta: "35 min",
    onStartNavigation: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders ETA and distance", () => {
    render(<RouteBottomCard {...defaultProps} />);
    expect(screen.getAllByText("35 min").length).toBeGreaterThan(0);
    expect(screen.getByText("(18.4 km)")).toBeInTheDocument();
  });

  it("renders Start button", () => {
    render(<RouteBottomCard {...defaultProps} />);
    expect(screen.getByText("Start")).toBeInTheDocument();
  });

  it("calls onStartNavigation when Start clicked", () => {
    render(<RouteBottomCard {...defaultProps} />);
    fireEvent.click(screen.getByText("Start"));
    expect(defaultProps.onStartNavigation).toHaveBeenCalled();
  });

  it("shows signal strength label", () => {
    render(<RouteBottomCard {...defaultProps} />);
    expect(screen.getByText(/Strong Signal/)).toBeInTheDocument();
  });

  it("shows zone count", () => {
    render(<RouteBottomCard {...defaultProps} />);
    expect(screen.getByText("3 zones")).toBeInTheDocument();
  });

  it("shows route name", () => {
    render(<RouteBottomCard {...defaultProps} />);
    expect(screen.getByText("via Route 1 via Hosur Road")).toBeInTheDocument();
  });

  it("shows Suggested badge when suggested prop is true", () => {
    render(<RouteBottomCard {...defaultProps} suggested={true} />);
    expect(screen.getByText("Suggested")).toBeInTheDocument();
  });

  it("does not show Suggested badge by default", () => {
    render(<RouteBottomCard {...defaultProps} />);
    expect(screen.queryByText("Suggested")).not.toBeInTheDocument();
  });

  it("shows weak signal for low score routes", () => {
    const weakRoute = { ...mockRoute, signal_score: 25 };
    render(
      <RouteBottomCard {...defaultProps} route={weakRoute} />,
    );
    expect(screen.getByText(/Weak Signal/)).toBeInTheDocument();
  });
});
