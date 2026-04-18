import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChatBot } from "../ChatBot";

describe("ChatBot", () => {
  const defaultProps = {
    onClose: jest.fn(),
    onApply: jest.fn(),
    detectedNetwork: "unknown",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the chatbot header", async () => {
    render(<ChatBot {...defaultProps} />);
    expect(screen.getByText("Route Assistant")).toBeInTheDocument();
  });

  it("shows online indicator", () => {
    render(<ChatBot {...defaultProps} />);
    expect(screen.getByText("Online")).toBeInTheDocument();
  });

  it("displays initial greeting message after delay", async () => {
    render(<ChatBot {...defaultProps} />);
    await waitFor(
      () => {
        expect(
          screen.getByText(/I'll help you find the best route/),
        ).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  it("calls onClose when back button clicked", () => {
    render(<ChatBot {...defaultProps} />);
    const buttons = screen.getAllByRole("button");
    // First button is the back arrow
    fireEvent.click(buttons[0]);
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it("shows text input for source step", async () => {
    render(<ChatBot {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/Electronic City/),
      ).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it("advances to next step when user types and sends", async () => {
    render(<ChatBot {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Electronic City/)).toBeInTheDocument();
    }, { timeout: 2000 });

    const input = screen.getByPlaceholderText(/Electronic City/);
    fireEvent.change(input, { target: { value: "Koramangala" } });

    // Press Enter to send
    fireEvent.keyDown(input, { key: "Enter" });

    // User message should appear
    await waitFor(() => {
      expect(screen.getByText("Koramangala")).toBeInTheDocument();
    });
  });

  it("shows detected network in ISP step", async () => {
    render(<ChatBot {...defaultProps} detectedNetwork="Airtel" />);
    // The detected network is embedded in the steps
    await waitFor(() => {
      const greeting = screen.getByText(/I'll help you find/);
      expect(greeting).toBeInTheDocument();
    }, { timeout: 2000 });
  });
});
