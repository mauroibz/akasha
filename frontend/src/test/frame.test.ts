import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * One frame (Sprint 139, DEC-193): a page's width and its medium chooser are each
 * written once. These read the sources, because the rule is about where a thing is
 * written, not how one page renders.
 */
const root = join(__dirname, "..");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx$/.test(name) && !/\.test\.tsx$/.test(name) ? [path] : [];
  });
}

const files = sources(root).map((path) => ({
  path: path.slice(root.length + 1),
  text: readFileSync(path, "utf8"),
}));

describe("one frame", () => {
  it("writes <main> only in PageFrame and the sign-in frame", () => {
    const offenders = files
      .filter(({ text }) => /<main[\s>]/.test(text))
      .map(({ path }) => path);
    expect(offenders.sort()).toEqual([
      "components/AuthFrame.tsx",
      "components/PageFrame.tsx",
    ]);
  });

  it("writes the medium chooser only in DomainStrip", () => {
    const offenders = files
      .filter(({ text }) => text.includes('"Choose a domain"'))
      .map(({ path }) => path);
    expect(offenders).toEqual(["components/DomainStrip.tsx"]);
  });

  it("draws a cover's shape only in Cover, outside the screens with their own", () => {
    // The Library's virtualised card, the decks and the dialogs that crop or choose
    // a cover keep their own drawing; everything that lists covers goes through Cover.
    const through = [
      "pages/ShelfPage.tsx",
      "pages/DiaryPage.tsx",
      "pages/YearReviewPage.tsx",
      "pages/LentPage.tsx",
      "features/pile/PilePage.tsx",
      "features/diary/Timeline.tsx",
      "features/home/UpNext.tsx",
      "features/home/SuggestedModule.tsx",
      "features/home/QuestionModule.tsx",
    ];
    const offenders = files
      .filter(({ path }) => through.includes(path))
      .filter(({ text }) => text.includes("aspect-[2/3]"))
      .map(({ path }) => path);
    expect(offenders).toEqual([]);
  });
});
