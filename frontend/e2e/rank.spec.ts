import { expect, test } from "./console";
import { stubRank } from "./rank-fixture";

/** A rank inside a score, chosen two at a time (Sprint 116, DEC-176). */

for (const size of [
  { name: "a phone", width: 390, height: 664 },
  { name: "a desktop", width: 1440, height: 900 },
]) {
  test(`on ${size.name} the two covers and the answers fit`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await stubRank(page);
    await page.goto("/rank/book/8");
    await expect(
      page.getByRole("heading", { name: "Which did you like more?" }),
    ).toBeVisible();
    for (const name of ["Solaris", "Stoner", "About the same"]) {
      const box = (await page
        .getByRole("button", { name, exact: true })
        .boundingBox())!;
      expect(box.x + box.width, `${name} right`).toBeLessThanOrEqual(
        size.width,
      );
      expect(box.y + box.height, `${name} bottom`).toBeLessThanOrEqual(
        size.height,
      );
      // Reachable means not under the phone's bottom navigation: what sits at the
      // control's centre is the control.
      const reachable = await page
        .getByRole("button", { name, exact: true })
        .evaluate((node) => {
          const rect = node.getBoundingClientRect();
          const hit = document.elementFromPoint(
            rect.x + rect.width / 2,
            rect.y + Math.min(rect.height / 2, 20),
          );
          return hit !== null && node.contains(hit);
        });
      expect(reachable, `${name} reachable`).toBe(true);
    }
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(size.width);
  });
}

test("four new eights are placed, from the keyboard, and the order is saved as it goes", async ({
  page,
}) => {
  const puts: Array<{ entry_ids: number[] }> = [];
  await stubRank(page, puts);
  await page.goto("/rank");
  await page.getByRole("link", { name: /8/ }).click();
  await expect(
    page.getByRole("heading", { name: "Which did you like more?" }),
  ).toBeVisible();
  // Prefer each newcomer to whatever it is asked against: it rises to the top.
  for (let asked = 0; asked < 12; asked++) {
    if (
      !(await page
        .getByRole("heading", { name: "Which did you like more?" })
        .isVisible())
    )
      break;
    await page.keyboard.press("ArrowLeft");
  }
  const order = page.getByRole("list", { name: "Your 8s, in order" });
  await expect(order.getByRole("listitem")).toHaveCount(5);
  await expect(order.getByRole("listitem").first()).toContainText("Piranesi");
  await expect(order.getByRole("listitem").last()).toContainText("Stoner");
  expect(puts).toHaveLength(4);
  expect(puts.at(-1)!.entry_ids).toEqual([5, 4, 3, 2, 1]);
});
