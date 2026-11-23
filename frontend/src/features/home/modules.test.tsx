import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Lately } from "./Lately";
import { LentOut } from "./LentOut";
import { QuestionModule } from "./QuestionModule";
import { ShelvesModule } from "./ShelvesModule";
import { entry, fullHome, renderWithRouter, types } from "./testHome";
import { TidyUp } from "./TidyUp";

afterEach(() => vi.restoreAllMocks());

describe("Lately", () => {
  it("lists finishes, score changes and additions, each opening its entry", () => {
    renderWithRouter(<Lately rows={fullHome().lately!} size="M" />);
    const module = screen.getByRole("region", { name: "Lately" });
    const items = within(module).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent(/Finished Pálido fuego/);
    expect(items[0]).toHaveTextContent("6 Nov");
    expect(items[1]).toHaveTextContent(/A Clash of Kings 8 → 6/);
    expect(items[2]).toHaveTextContent(/Added Why Nations Fail and 2 more/);
    expect(
      within(module).getByRole("link", { name: "Pálido fuego" }),
    ).toHaveAttribute("href", "/books/40");
    expect(within(module).getByRole("link", { name: /Diary/ })).toHaveAttribute(
      "href",
      "/diary",
    );
  });

  it("says a score kept is still that score, not a change to itself", () => {
    renderWithRouter(
      <Lately
        rows={[
          {
            kind: "score",
            at: "2026-11-23T10:00:00Z",
            entry: entry(70, "Pet Sematary", "book", { status: "read" }),
            score: 9,
            previous: 9,
            count: 1,
          },
        ]}
        size="M"
      />,
    );
    expect(screen.getByRole("listitem")).toHaveTextContent(
      /Pet Sematary still a 9/,
    );
  });

  it("shows fewer rows at a smaller size", () => {
    const rows = Array.from({ length: 8 }, (_, index) => ({
      kind: "finished" as const,
      at: `2026-11-0${index + 1}`,
      entry: entry(100 + index, `Book ${index}`, "book", { status: "read" }),
      score: null,
      previous: null,
      count: 1,
    }));
    const { unmount } = renderWithRouter(<Lately rows={rows} size="S" />);
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    unmount();
    renderWithRouter(<Lately rows={rows} size="L" />);
    expect(screen.getAllByRole("listitem")).toHaveLength(8);
  });
});

describe("TidyUp", () => {
  it("links each count to what resolves it", () => {
    renderWithRouter(
      <TidyUp
        tidy={{
          duplicates: 12,
          without_cover: 32,
          unscored: 3,
          unscored_by_type: { book: 3 },
        }}
        types={types}
      />,
    );
    const module = screen.getByRole("region", { name: "Tidy up" });
    expect(
      within(module).getByRole("link", { name: /12 possible duplicate pairs/ }),
    ).toHaveAttribute("href", "/deck/duplicates");
    expect(
      within(module).getByRole("link", { name: /32 without a cover/ }),
    ).toHaveAttribute("href", "/deck/covers");
    expect(
      within(module).getByRole("link", { name: /3 finished, not scored/ }),
    ).toHaveAttribute("href", "/library?type=book&status=read&unscored=true");
  });

  it("opens each library's unscored entries on their own, as the library shows one", () => {
    renderWithRouter(
      <TidyUp
        tidy={{
          duplicates: 0,
          without_cover: 0,
          unscored: 8,
          unscored_by_type: { book: 3, anime: 5 },
        }}
        types={types}
      />,
    );
    const module = screen.getByRole("region", { name: "Tidy up" });
    expect(module).toHaveTextContent(/8\s*finished, not scored/);
    expect(
      within(module).getByRole("link", { name: "3 books" }),
    ).toHaveAttribute("href", "/library?type=book&status=read&unscored=true");
    expect(
      within(module).getByRole("link", { name: "5 anime" }),
    ).toHaveAttribute(
      "href",
      "/library?type=anime&status=completed&unscored=true",
    );
  });

  it("leaves out a count of nothing", () => {
    renderWithRouter(
      <TidyUp
        tidy={{
          duplicates: 0,
          without_cover: 4,
          unscored: 0,
          unscored_by_type: {},
        }}
        types={types}
      />,
    );
    expect(within(screen.getByRole("list")).getAllByRole("link")).toHaveLength(
      1,
    );
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

describe("ShelvesModule", () => {
  it("opens each shelf, with its count", () => {
    renderWithRouter(<ShelvesModule shelves={fullHome().shelves!} size="S" />);
    expect(screen.getByRole("link", { name: "novela, 11" })).toHaveAttribute(
      "href",
      "/shelves/novela",
    );
    expect(screen.getByRole("link", { name: /All shelves/ })).toHaveAttribute(
      "href",
      "/shelves",
    );
  });
});

describe("LentOut", () => {
  it("names who has what, opening the entry", () => {
    renderWithRouter(<LentOut lent={fullHome().lent!} size="S" />);
    const module = screen.getByRole("region", { name: "Lent out" });
    expect(
      within(module).getByRole("link", { name: "Rayuela" }),
    ).toHaveAttribute("href", "/books/44");
    expect(within(module).getAllByRole("listitem")[0]).toHaveTextContent(/Ana/);
    expect(within(module).getByRole("link", { name: /2 out/ })).toHaveAttribute(
      "href",
      "/lent",
    );
  });
});
