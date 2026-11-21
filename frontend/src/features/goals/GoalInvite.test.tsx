import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ItemType } from "@/api/library";

import { GoalInvite } from "./GoalInvite";

const book = { id: "book", label: "Book", plural_label: "Books" } as ItemType;

function invite(done: number) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <GoalInvite domain={book} done={done} year={2026} onOther={() => {}} />
    </QueryClientProvider>
  );
}

describe("GoalInvite", () => {
  it("follows the suggestions when the year's count arrives after the first render", () => {
    // The Diary renders before the year's finishes load (0), then again with them.
    // The middle suggestion was kept from the first render, so the button offered
    // "Aim for 12" beside picks of 24, 36 and 52, none of them selected (Sprint 129).
    const { rerender } = render(invite(0));
    expect(
      screen.getByRole("button", { name: "Aim for 12" }),
    ).toBeInTheDocument();

    rerender(invite(20));
    expect(
      screen.getByRole("button", { name: "Aim for 36" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^36/, pressed: true }),
    ).toBeInTheDocument();
  });
});
