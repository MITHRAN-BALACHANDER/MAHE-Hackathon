import { renderHook, act } from "@testing-library/react";
import { useAuth } from "../useAuth";
import { AuthProvider } from "../../providers/AuthProvider";
import { useRouter } from "next/navigation";
import React from "react";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
  usePathname: jest.fn(),
}));

describe("useAuth", () => {
  const mockPush = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    localStorage.clear();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  it("initializes to false when no token", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("initializes to true when token exists in localStorage", () => {
    localStorage.setItem("token", "fake-token");
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("updates state and localStorage when login is called", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.setToken("new-token");
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(localStorage.getItem("token")).toBe("new-token");
  });

  it("updates state and localStorage when logout is called", () => {
    localStorage.setItem("token", "fake-token");
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorage.getItem("token")).toBeNull();
  });
});
