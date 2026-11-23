import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Cover } from "@/components/Cover";

describe("Cover", () => {
  it("draws the image at the asked size with an empty alt beside a caption", () => {
    const { container } = render(
      <Cover src="/c.png" size="m" title="Rayuela" creator="Julio Cortázar" />,
    );
    expect(container.querySelector("img")).toHaveAttribute("alt", "");
    expect(container.firstElementChild).toHaveAttribute("data-size", "m");
    expect(screen.getByText("Rayuela")).toBeInTheDocument();
    expect(screen.getByText("Julio Cortázar")).toBeInTheDocument();
  });

  it("names the image itself when there is no caption", () => {
    render(<Cover src="/c.png" size="s" alt="Rayuela" />);
    expect(screen.getByRole("img", { name: "Rayuela" })).toBeInTheDocument();
  });

  it("shows a score beside the caption when there is one", () => {
    render(<Cover src={null} size="m" title="Rayuela" score={9} />);
    expect(screen.getByText("9")).toBeInTheDocument();
  });
});
