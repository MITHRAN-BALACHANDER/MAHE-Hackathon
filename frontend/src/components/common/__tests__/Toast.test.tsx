import { render, screen, fireEvent } from "@testing-library/react";
import { Toast } from "../Toast";

describe("Toast", () => {
  it("renders message when provided", () => {
    render(<Toast message="Signal dropping ahead" />);
    expect(screen.getByText("Signal dropping ahead")).toBeInTheDocument();
  });

  it("returns null when message is null", () => {
    const { container } = render(<Toast message={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("dismisses when X button clicked", () => {
    render(<Toast message="Test alert" />);
    expect(screen.getByText("Test alert")).toBeInTheDocument();

    const closeBtn = screen.getByRole("button");
    fireEvent.click(closeBtn);

    expect(screen.queryByText("Test alert")).not.toBeInTheDocument();
  });

  it("shows warning styling for warning type", () => {
    const { container } = render(
      <Toast message="Dead zone ahead" type="warning" />,
    );
    const toast = container.firstChild as HTMLElement;
    expect(toast.className).toContain("bg-yellow-50");
  });

  it("shows reroute styling for reroute type", () => {
    const { container } = render(
      <Toast message="Rerouting..." type="reroute" />,
    );
    const toast = container.firstChild as HTMLElement;
    expect(toast.className).toContain("bg-blue-50");
  });

  it("shows default styling for info type", () => {
    const { container } = render(
      <Toast message="Info message" type="info" />,
    );
    const toast = container.firstChild as HTMLElement;
    expect(toast.className).toContain("bg-white");
  });
});
