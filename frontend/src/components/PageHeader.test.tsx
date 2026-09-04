import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PageHeader } from "@/components/PageHeader";

/**
 * The one page-header idiom (proposal §3.2): eyebrow, title, optional count, lede,
 * an actions slot, and — when asked for one — the single "← Library" way back that
 * replaces the four spellings finding 8 catalogued.
 */
describe("PageHeader", () => {
  it("renders an eyebrow, a title, a count and a lede", () => {
    render(
      <MemoryRouter>
        <PageHeader
          eyebrow="Triage"
          title="Inbox"
          count="12 unsorted"
          lede="What just landed."
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("Triage")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: /inbox\s*12 unsorted/i }),
    ).toBeVisible();
    expect(screen.getByText("What just landed.")).toBeVisible();
  });

  it("renders the actions slot", () => {
    render(
      <MemoryRouter>
        <PageHeader
          title="Shelves"
          actions={<button type="button">Create shelf</button>}
        />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: "Create shelf" }),
    ).toBeVisible();
  });

  it("renders no back control unless asked for one", () => {
    render(
      <MemoryRouter>
        <PageHeader title="Insights" />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("link", { name: /library/i })).toBeNull();
  });

  it("renders the one way back, reading the same wherever it appears", () => {
    render(
      <MemoryRouter>
        <PageHeader title="Shelves" back />
      </MemoryRouter>,
    );
    const back = screen.getByRole("link", { name: "← Library" });
    expect(back).toHaveAttribute("href", "/");
  });
});
