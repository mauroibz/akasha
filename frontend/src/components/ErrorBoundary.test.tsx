import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Link, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RoutedErrorBoundary } from "@/components/ErrorBoundary";
import { RouteErrorPage } from "@/pages/NotFoundPage";

/**
 * React logs every error it hands to a boundary, so a test that deliberately
 * throws would otherwise spray a component stack across the run and hide real
 * failures.
 */
beforeEach(() =>
  vi.spyOn(console, "error").mockImplementation(() => undefined),
);
afterEach(() => vi.restoreAllMocks());

let shouldThrow = true;

function Boom() {
  if (shouldThrow) throw new Error("the route exploded");
  return <p>Recovered content</p>;
}

function renderApp(initial = "/broken") {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Link to="/safe">Go somewhere else</Link>
      <RoutedErrorBoundary
        fallback={(error, reset) => (
          <RouteErrorPage error={error} reset={reset} />
        )}
      >
        <Routes>
          <Route path="/broken" element={<Boom />} />
          <Route path="/safe" element={<p>A perfectly fine page</p>} />
        </Routes>
      </RoutedErrorBoundary>
    </MemoryRouter>,
  );
}

describe("RoutedErrorBoundary", () => {
  beforeEach(() => {
    shouldThrow = true;
  });

  it("renders the route fallback instead of an empty screen", () => {
    renderApp();
    expect(screen.getByRole("heading", { name: /went wrong/i })).toBeVisible();
    // The failure has to say something. A blank page and a silent console is
    // the failure mode this boundary exists to prevent.
    expect(screen.getByText(/the route exploded/)).toBeVisible();
  });

  it("re-renders the route when the fallback's retry is used", async () => {
    const user = userEvent.setup();
    renderApp();
    shouldThrow = false;
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(screen.getByText("Recovered content")).toBeVisible();
  });

  it("clears the caught error when the route changes", async () => {
    const user = userEvent.setup();
    renderApp();
    expect(screen.getByRole("heading", { name: /went wrong/i })).toBeVisible();
    // Navigating away is the escape hatch. Before the boundary was keyed on the
    // pathname it kept its error forever, so the fallback covered every later
    // page and a reload was the only way out.
    await user.click(screen.getByRole("link", { name: /somewhere else/i }));
    expect(screen.getByText("A perfectly fine page")).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: /went wrong/i }),
    ).not.toBeInTheDocument();
  });
});
