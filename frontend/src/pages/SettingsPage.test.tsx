import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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
    // The presets (Sprint 148): six themes and the device's own choice.
    expect(
      screen.getAllByRole("radio", { name: /./ }).length,
    ).toBeGreaterThanOrEqual(7);
    await userEvent.click(screen.getByRole("radio", { name: /^moss/i }));
    expect(screen.getByRole("radio", { name: /^moss/i })).toBeChecked();
    expect(document.documentElement.dataset.theme).toBe("moss");
    expect(localStorage.getItem("akasha:theme")).toBe("moss");
  });

  it("says which suggestion sources are on, and what the model is sent", async () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }));
    const types = [
      {
        id: "book",
        recommendation: {
          sources: [
            {
              name: "model",
              label: "Model",
              configured: false,
              hint: "Set AKASHA_RECS_MODEL_KEY and restart.",
              resolved_only: true,
              about: {
                provider: "anthropic",
                provider_label: "Claude",
                model: "claude-haiku-5-5",
                sends:
                  "Titles, creators, years and your scores from this library; nothing else.",
              },
            },
          ],
          attribution: {},
        },
      },
      {
        id: "movie",
        recommendation: {
          sources: [
            { name: "tmdb", label: "TMDB", configured: true, hint: null },
            {
              name: "model",
              label: "Model",
              configured: false,
              hint: "Set AKASHA_RECS_MODEL_KEY and restart.",
            },
          ],
          attribution: {},
        },
      },
    ];
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input) =>
        new Response(
          String(input).includes("/api/item-types")
            ? JSON.stringify(types)
            : "[]",
        ),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <SettingsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const section = await screen.findByRole("region", { name: "Suggestions" });
    const rows = within(section).getAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringMatching(/^ModelOff.*Claude · claude-haiku-5-5/),
      expect.stringMatching(/^TMDBOn/),
    ]);
    expect(
      within(section).getByText(
        "What it is sent: Titles, creators, years and your scores from this library; nothing else.",
      ),
    ).toBeVisible();
    expect(
      within(section).getByText("Set AKASHA_RECS_MODEL_KEY and restart."),
    ).toBeVisible();
  });
});
