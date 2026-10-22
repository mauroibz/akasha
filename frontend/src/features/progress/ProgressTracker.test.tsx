import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ItemType, LibraryEntry } from "@/api/library";
import { mockApi } from "@/test/mockApi";
import { HowFarDialog } from "./HowFarDialog";
import { ProgressTracker } from "./ProgressTracker";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const series = {
  id: "series",
  label: "Series",
  fields: [
    {
      name: "season_episodes",
      label: "Episodes per season",
      type: "rows",
      multiplicity: "many",
      columns: [
        { name: "season", label: "Season", type: "number" },
        { name: "episodes", label: "Episodes", type: "number" },
      ],
    },
  ],
  statuses: [
    { value: "watching", label: "Watching", choosable: true, hotkey: "w" },
    {
      value: "dropped",
      label: "Dropped",
      choosable: true,
      hotkey: "d",
      abandoned: true,
    },
  ],
  progress: {
    label: "Episodes watched",
    unit_label: "episode",
    total_field: "episodes",
    parts_field: "season_episodes",
  },
} as unknown as ItemType;

const book = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [],
  progress: {
    label: "Chapters read",
    unit_label: "chapter",
    total_field: "chapters",
    parts_field: null,
  },
} as unknown as ItemType;

const movie = {
  id: "movie",
  label: "Movie",
  fields: [],
  statuses: [],
  progress: null,
} as unknown as ItemType;

const types = [series, book, movie];

function entryOf(
  overrides: Omit<Partial<LibraryEntry>, "item"> & { item?: object },
) {
  const { item, ...rest } = overrides;
  return {
    id: 7,
    item_id: 3,
    status: "watching",
    progress: null,
    progress_marks: null,
    ...rest,
    item: {
      id: 3,
      type: "series",
      title: "Breaking Bad",
      metadata: {
        season_episodes: [
          { season: 1, episodes: 3 },
          { season: 2, episodes: 4 },
        ],
      },
      outline: [
        { part: 1, size: 3 },
        { part: 2, size: 4 },
      ],
      ...item,
    },
  } as unknown as LibraryEntry;
}

function patches(fetchMock: ReturnType<typeof mockApi>, url: string) {
  return fetchMock.mock.calls
    .filter(
      ([input, init]) => String(input) === url && init?.method === "PATCH",
    )
    .map(([, init]) => JSON.parse(String(init?.body)));
}

function show(node: React.ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      {node}
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("ProgressTracker", () => {
  it("is one closed line until opened", async () => {
    mockApi(() => undefined);
    show(<ProgressTracker entry={entryOf({ progress: 5 })} types={types} />);
    expect(screen.getByText("5 / 7 episodes")).toBeInTheDocument();
    const line = screen.getByRole("button", { name: /Show episodes/ });
    expect(line).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    await userEvent.setup().click(line);
    expect(line).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("group")).toBeInTheDocument();
  });

  it("draws an imported count as the first episodes and stores them on first touch", async () => {
    const fetchMock = mockApi((input) =>
      String(input).endsWith("/api/entries/7") ? json(entryOf({})) : undefined,
    );
    const user = userEvent.setup();
    show(<ProgressTracker entry={entryOf({ progress: 5 })} types={types} />);
    await user.click(screen.getByRole("button", { name: /Show episodes/ }));
    expect(
      screen.getByRole("button", { name: "Season 2, episode 2" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: "Season 2, episode 3" }),
    ).toHaveAttribute("aria-pressed", "false");

    await user.click(
      screen.getByRole("button", { name: "Season 2, episode 4" }),
    );
    await waitFor(() =>
      expect(patches(fetchMock, "/api/entries/7")).toEqual([
        { progress_marks: { "1": [1, 2, 3], "2": [1, 2, 4] } },
      ]),
    );
  });

  it("marks a whole season with its label, and clears a full one", async () => {
    const fetchMock = mockApi((input) =>
      String(input).endsWith("/api/entries/7") ? json(entryOf({})) : undefined,
    );
    const user = userEvent.setup();
    show(
      <ProgressTracker
        entry={entryOf({
          progress: 4,
          progress_marks: { "1": [1, 2, 3], "2": [1] },
        })}
        types={types}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Show episodes/ }));
    await user.click(
      screen.getByRole("button", { name: "Mark all of season 2" }),
    );
    await user.click(screen.getByRole("button", { name: "Clear season 1" }));
    await waitFor(() =>
      expect(patches(fetchMock, "/api/entries/7")).toEqual([
        { progress_marks: { "1": [1, 2, 3], "2": [1, 2, 3, 4] } },
        { progress_marks: { "2": [1, 2, 3, 4] } },
      ]),
    );
  });

  it("offers to load the episode list for a series that has none", async () => {
    const fetchMock = mockApi((input) =>
      String(input).endsWith("/api/items/3/outline")
        ? json({ error: { code: "outline_unavailable", message: "x" } }, 422)
        : undefined,
    );
    const user = userEvent.setup();
    show(
      <ProgressTracker
        entry={entryOf({
          item: {
            metadata: { episodes: 62 },
            outline: [{ part: 1, size: 62 }],
          },
        })}
        types={types}
      />,
    );
    expect(screen.getByText("0 / 62 episodes")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Show episodes/ }));
    await user.click(
      screen.getByRole("button", { name: "Load the episode list" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/items/3/outline",
      expect.objectContaining({ method: "POST" }),
    );
    expect(
      await screen.findByText("No episode list was found for this one."),
    ).toBeInTheDocument();
  });

  it("lets a book be given its chapter count", async () => {
    const fetchMock = mockApi((input) =>
      String(input).endsWith("/api/items/3") ? json({}) : undefined,
    );
    const user = userEvent.setup();
    show(
      <ProgressTracker
        entry={entryOf({
          item: { type: "book", title: "Rayuela", metadata: {}, outline: null },
        })}
        types={types}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Set/ }));
    await user.type(screen.getByLabelText("How many chapters?"), "155");
    await user.click(screen.getByRole("button", { name: "Add chapters" }));
    await waitFor(() =>
      expect(patches(fetchMock, "/api/items/3")).toEqual([
        { metadata: { chapters: 155 } },
      ]),
    );
  });

  it("takes a typed count where there are no lights to draw", async () => {
    const fetchMock = mockApi((input) =>
      String(input).endsWith("/api/entries/7") ? json(entryOf({})) : undefined,
    );
    const user = userEvent.setup();
    show(
      <ProgressTracker
        entry={entryOf({
          progress: 4,
          item: { type: "series", metadata: {}, outline: null },
        })}
        types={types}
      />,
    );
    expect(screen.getByText("4 episodes")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Set/ }));
    const count = screen.getByLabelText("Episodes watched");
    await user.clear(count);
    await user.type(count, "9");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(patches(fetchMock, "/api/entries/7")).toEqual([{ progress: 9 }]),
    );
  });

  it("is absent where the domain counts no progress", () => {
    mockApi(() => undefined);
    show(
      <ProgressTracker
        entry={entryOf({ item: { type: "movie", outline: null } })}
        types={types}
      />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("HowFarDialog", () => {
  it("lights everything through the last episode finished and saves it", async () => {
    const fetchMock = mockApi((input) =>
      String(input).endsWith("/api/entries/7") ? json(entryOf({})) : undefined,
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    show(
      <HowFarDialog
        entry={entryOf({ status: "dropped" })}
        types={types}
        onClose={onClose}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "How far did you get?" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Season 2, episode 2" }),
    );
    expect(screen.getByText("5 of 7 episodes")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(patches(fetchMock, "/api/entries/7")).toEqual([
        { progress_marks: { "1": [1, 2, 3], "2": [1, 2] } },
      ]),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("writes nothing on Skip", async () => {
    const fetchMock = mockApi(() => undefined);
    const onClose = vi.fn();
    const user = userEvent.setup();
    show(
      <HowFarDialog
        entry={entryOf({ status: "dropped" })}
        types={types}
        onClose={onClose}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Skip" }));
    expect(onClose).toHaveBeenCalled();
    expect(patches(fetchMock, "/api/entries/7")).toEqual([]);
  });

  it("asks for a count where there is no outline", async () => {
    const fetchMock = mockApi((input) =>
      String(input).endsWith("/api/entries/7") ? json(entryOf({})) : undefined,
    );
    const user = userEvent.setup();
    show(
      <HowFarDialog
        entry={entryOf({
          status: "dropped",
          item: { type: "book", title: "Rayuela", metadata: {}, outline: null },
        })}
        types={types}
        onClose={vi.fn()}
      />,
    );
    await user.type(screen.getByLabelText("Chapters read"), "12");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(patches(fetchMock, "/api/entries/7")).toEqual([{ progress: 12 }]),
    );
  });
});
