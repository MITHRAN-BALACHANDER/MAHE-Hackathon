import "@testing-library/jest-dom";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock next/dynamic
jest.mock("next/dynamic", () => ({
  __esModule: true,
  default: (loader: () => Promise<any>) => {
    const Component = (props: any) => null;
    Component.displayName = "DynamicComponent";
    return Component;
  },
}));

// Mock framer-motion
const React = require("react");
jest.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => React.createElement("div", props, children),
    button: ({ children, ...props }: any) => React.createElement("button", props, children),
  },
  AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
}));

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  observe = jest.fn();
  disconnect = jest.fn();
  unobserve = jest.fn();
} as any;

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
    get length() { return Object.keys(store).length; },
    key: (i: number) => Object.keys(store)[i] || null,
  };
})();
Object.defineProperty(window, "localStorage", { value: localStorageMock });

// Suppress act() warnings
const originalError = console.error;
console.error = (...args: any[]) => {
  if (typeof args[0] === "string" && args[0].includes("act(")) return;
  originalError.call(console, ...args);
};
