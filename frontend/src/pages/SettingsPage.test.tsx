import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./SettingsPage";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.theme;
});

describe("SettingsPage", () => {
  it("switches the page to the theme chosen and remembers it", async () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }));
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response("[]"),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <SettingsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      screen.getByRole("radio", { name: /match my device/i }),
    ).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: /^paper/i }));
    expect(document.documentElement.dataset.theme).toBe("paper");
    expect(localStorage.getItem("akasha:theme")).toBe("paper");
  });
});
