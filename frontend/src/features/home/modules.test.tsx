import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Lately } from "./Lately";
import { QuestionModule } from "./QuestionModule";
import { entry, fullHome, renderWithRouter, types } from "./testHome";

afterEach(() => vi.restoreAllMocks());

describe("Lately", () => {
  it("is a row of covers: finishes, score changes and additions, each opening its entry", () => {
    renderWithRouter(<Lately rows={fullHome().lately} />);
    const band = screen.getByRole("region", { name: "Lately" });
    const items = within(band).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Pálido fuego");
    expect(items[0]).toHaveTextContent("Finished");
    expect(items[1]).toHaveTextContent("A Clash of Kings");
    expect(items[1]).toHaveTextContent("8 → 6");
    expect(items[2]).toHaveTextContent("Added +2");
    expect(
      within(band).getByRole("link", {
        name: /Score changed from 8 to 6: A Clash of Kings/,
      }),
    ).toBeVisible();
    expect(
      within(band).getByRole("link", { name: /Finished: Pálido fuego, 6 Nov/ }),
    ).toHaveAttribute("href", "/books/40");
  });

  it("dates an addition by the person's own day, not the stored UTC one", () => {
    const zone = process.env.TZ;
    process.env.TZ = "America/Argentina/Buenos_Aires";
    try {
      const rows = fullHome().lately.map((row) =>
        row.kind === "added" ? { ...row, at: "2026-10-03T01:30:00Z" } : row,
      );
      renderWithRouter(<Lately rows={rows} />);
      expect(
        screen.getByRole("link", { name: /Why Nations Fail, 2 Oct/ }),
      ).toBeInTheDocument();
    } finally {
      process.env.TZ = zone;
    }
  });

  it("says a score kept is still that score, not a change to itself", () => {
    renderWithRouter(
      <Lately
        rows={[
          {
            kind: "score",
            at: "2026-11-01T10:00:00Z",
            entry: entry(50, "Dune", "book", { status: "read", score: 9 }),
            score: 9,
            previous: 9,
            count: 1,
          },
        ]}
      />,
    );
    expect(screen.getByRole("listitem")).toHaveTextContent("Still");
    expect(screen.getByRole("listitem")).not.toHaveTextContent("→");
  });

  it("draws nothing when nothing happened", () => {
    const { container } = renderWithRouter(<Lately rows={[]} />);
    expect(container.querySelector("section")).toBeNull();
  });
});

describe("QuestionModule", () => {
  it("asks whether an old score still holds and keeps it in a tap", async () => {
    const bodies: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        if (init?.method === "PATCH")
          bodies.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify(fullHome().question!.entry));
      }),
    );
    renderWithRouter(
      <QuestionModule question={fullHome().question!} types={types} />,
    );
    expect(
      screen.getByRole("heading", { name: "Is Pet Sematary still a 9?" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Change" })).toHaveAttribute(
      "href",
      "/deck/revisit",
    );
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Still a 9" }));
    await waitFor(() =>
      expect(bodies).toEqual([{ score: 9, score_reason: "time" }]),
    );
  });

  it("asks a gap's question in place", () => {
    renderWithRouter(
      <QuestionModule
        question={{
          kind: "gap",
          entry: entry(50, "Rayuela", "book", { status: "read" }),
          scored_at: null,
        }}
        types={types}
      />,
    );
    const module = screen.getByRole("region", { name: "One question" });
    expect(within(module).getByText("Rayuela")).toBeVisible();
    expect(within(module).getByText("When did you finish it?")).toBeVisible();
  });
});
