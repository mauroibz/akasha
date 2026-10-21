import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SaveView } from "./SaveView";

afterEach(() => vi.restoreAllMocks());

describe("SaveView", () => {
  it("keeps the library's current filters under the name typed", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({ id: 4, name: "Vinyl", query: "type=album" }),
          { status: 201 },
        ),
      );
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SaveView query="type=album&status=owned" />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Save view" }));
    await user.type(screen.getByLabelText("View name"), "Vinyl{Enter}");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/views",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Vinyl",
          query: "type=album&status=owned",
        }),
      }),
    );
    expect(
      await screen.findByRole("button", { name: "Save view" }),
    ).toBeVisible();
  });
});
