import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DomainStrip } from "@/components/DomainStrip";

/**
 * The one domain-strip idiom (proposal §3.3), extracted from the library's and
 * insights' near-identical radiogroups (finding 9) — and the component that pays
 * DEC-134's 390px overflow once, for both screens, by scrolling within itself
 * rather than pushing the document sideways.
 */
describe("DomainStrip", () => {
  const domains = [
    { id: "book", label: "Book" },
    { id: "album", label: "Album" },
    { id: "anime", label: "Anime" },
    { id: "movie", label: "Movie" },
    { id: "series", label: "Series" },
  ];

  it("renders the declared domains and marks the active one", () => {
    render(
      <DomainStrip domains={domains} value="album" onChange={() => undefined} />,
    );
    const strip = screen.getByRole("radiogroup", { name: "Choose a domain" });
    const radios = within(strip).getAllByRole("radio");
    expect(radios.map((radio) => radio.textContent)).toEqual([
      "Book",
      "Album",
      "Anime",
      "Movie",
      "Series",
    ]);
    expect(screen.getByRole("radio", { name: "Album" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("radio", { name: "Book" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("calls back with the chosen domain's id", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DomainStrip domains={domains} value="book" onChange={onChange} />);
    await user.click(screen.getByRole("radio", { name: "Series" }));
    expect(onChange).toHaveBeenCalledWith("series");
  });

  it("scrolls within itself rather than growing past its own box, at any domain count", () => {
    render(
      <DomainStrip domains={domains} value="book" onChange={() => undefined} />,
    );
    const strip = screen.getByRole("radiogroup", { name: "Choose a domain" });
    expect(strip.className).toMatch(/overflow-x-auto/);
    expect(strip.className).toMatch(/max-w-full/);
  });

  it("keeps a 44px target on every domain button", () => {
    render(
      <DomainStrip domains={domains} value="book" onChange={() => undefined} />,
    );
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio.className).toMatch(/min-h-11/);
    }
  });
});
