import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CoverImage } from "@/components/CoverImage";

/**
 * jsdom applies no CSS, so nothing here can prove the absence of layout shift.
 * What it can prove is the structural property the absence follows from: the
 * box comes from the caller's classes on a wrapper that exists before a single
 * byte of the image has arrived, and the image is never what sizes it.
 *
 * The geometric proof is in `e2e/library.spec.ts`, against a cover that
 * deliberately arrives late.
 */
describe("CoverImage", () => {
  const size = "h-48 w-32";

  it("carries the caller's box in every state", () => {
    const { rerender, container } = render(
      <CoverImage
        src="/covers/1.jpg"
        alt="Cover of Rayuela"
        className={size}
      />,
    );
    expect(container.firstElementChild?.className).toContain(size);

    fireEvent.load(screen.getByRole("img", { name: "Cover of Rayuela" }));
    expect(container.firstElementChild?.className).toContain(size);

    rerender(<CoverImage src={null} alt="Cover of Rayuela" className={size} />);
    expect(container.firstElementChild?.className).toContain(size);
  });

  it("reports its loading state so the box can be measured mid-flight", () => {
    render(
      <CoverImage
        src="/covers/1.jpg"
        alt="Cover of Rayuela"
        className={size}
      />,
    );
    const image = screen.getByRole("img", { name: "Cover of Rayuela" });
    expect(image).toHaveAttribute("data-cover-state", "loading");
    fireEvent.load(image);
    expect(image).toHaveAttribute("data-cover-state", "loaded");
  });

  it("falls back to a placeholder when the image fails", () => {
    render(
      <CoverImage
        src="/covers/gone.jpg"
        alt="Cover of Rayuela"
        className={size}
      />,
    );
    fireEvent.error(screen.getByRole("img", { name: "Cover of Rayuela" }));
    expect(screen.getByLabelText("Cover failed to load")).toBeInTheDocument();
  });

  it("keeps the skeleton out of flow so it cannot displace anything", () => {
    const { container } = render(
      <CoverImage
        src="/covers/1.jpg"
        alt="Cover of Rayuela"
        className={size}
      />,
    );
    const skeleton = container.querySelector("[aria-hidden='true']");
    expect(skeleton?.className).toContain("absolute inset-0");
  });
});
