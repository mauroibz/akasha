import type { InsightRow, InsightSummary } from "@/api/library";
import type { ChronologyBucket } from "@/features/library/insights";

/**
 * The insights page, read back as sentences (Sprint 102, DEC-169).
 *
 * Every sentence is built here from data the page already holds, as a list of
 * segments so the page can set the figures apart without parsing a string. Pure
 * and domain-agnostic: the noun comes in as a function (`countLabel`), never as
 * a word this module chooses.
 */
export interface Segment {
  text: string;
  /** A figure the eye should land on. */
  em?: boolean;
}

export type Noun = (count: number) => string;

const em = (text: string): Segment => ({ text, em: true });
const plain = (text: string): Segment => ({ text });

/** "one", "two" … "nine", then digits: small counts read better as words. */
const words = [
  "no",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
];
export function spelled(count: number): string {
  return count < words.length ? words[count] : count.toLocaleString();
}

/** The most common score; a tie goes to the higher score. `null` when none. */
export function modalScore(counts: number[]): number | null {
  let best: number | null = null;
  counts.forEach((count, index) => {
    if (count === 0) return;
    if (best === null || count >= counts[best - 1]) best = index + 1;
  });
  return best;
}

/** How many scores the lead sentence needs before it judges how you rate. */
const judgedFrom = 5;

export function leadSentence(params: {
  summary: InsightSummary;
  noun: Noun;
  /** The leading ranked row, when one leads by more than one entry. */
  leader?: Pick<InsightRow, "label" | "count">;
}): Segment[] {
  const { summary, noun, leader } = params;
  const parts: Segment[] = [plain("You keep "), em(noun(summary.held))];
  if (summary.finished > 0) {
    parts.push(
      plain(" and have finished "),
      em(summary.finished.toLocaleString()),
    );
  }
  parts.push(plain("."));
  // A judgement, not the figure: the rating section states the figure, and
  // a handful of scores is too few to judge from.
  if (summary.modal_score !== null && summary.rated >= judgedFrom) {
    if (summary.modal_score >= 8)
      parts.push(plain(" You rate "), em("generously"), plain("."));
    else if (summary.modal_score <= 5)
      parts.push(plain(" You rate "), em("hard"), plain("."));
  }
  if (leader && leader.count > 1) {
    parts.push(plain(" You return most to "), em(leader.label), plain("."));
  }
  return parts;
}

export function ratingSentence(counts: number[]): Segment[] | null {
  const modal = modalScore(counts);
  if (modal === null) return null;
  const parts: Segment[] = [
    plain("Most of what you rate lands at "),
    em(String(modal)),
    plain("."),
  ];
  const tens = counts[9];
  const lowest = counts.findIndex((count) => count > 0) + 1;
  if (tens > 0 && modal !== 10) {
    parts.push(
      plain(` You have given ${spelled(tens)} `),
      em(tens === 1 ? "10" : "10s"),
    );
    if (lowest > 1)
      parts.push(plain(", and nothing below a "), em(String(lowest)));
    parts.push(plain("."));
  } else if (lowest > 1) {
    parts.push(plain(" Nothing is below a "), em(String(lowest)), plain("."));
  }
  return parts;
}

export function rankedSentence(
  row: InsightRow,
  sort: "count" | "score",
  noun: Noun,
): Segment[] {
  if (sort === "score" && row.mean_score !== null) {
    return [
      em(row.label),
      plain(" has your best average: "),
      em(row.mean_score.toFixed(1)),
      plain(` over ${noun(row.rated_count)}.`),
    ];
  }
  return [
    plain("You return most to "),
    em(row.label),
    plain(": "),
    em(noun(row.count)),
    plain("."),
  ];
}

export function termsSentence(rows: InsightRow[]): Segment[] {
  const top = rows.slice(0, 3);
  if (top.length === 0) return [];
  const parts: Segment[] = [plain("Mostly ")];
  top.forEach((row, index) => {
    if (index > 0) parts.push(plain(index === top.length - 1 ? " and " : ", "));
    parts.push(em(row.label));
  });
  parts.push(plain("."));
  return parts;
}

export function chronologySentence(
  buckets: ChronologyBucket[],
  earliest: InsightSummary["earliest"],
): Segment[] {
  const total = buckets.reduce((sum, bucket) => sum + bucket.count, 0);
  if (total === 0) return [];
  const parts: Segment[] = [];
  let fromNewest = 0;
  for (let index = buckets.length - 1; index >= 0; index -= 1) {
    fromNewest += buckets[index].count;
    if (fromNewest * 2 >= total) {
      const bucket = buckets[index];
      parts.push(
        plain("Half of them are from the "),
        em(bucket.label),
        plain(index === buckets.length - 1 ? "." : " or later."),
      );
      break;
    }
  }
  if (earliest) {
    parts.push(
      plain(" The oldest is "),
      em(earliest.title),
      plain(", from "),
      em(String(earliest.year)),
      plain("."),
    );
  }
  return parts;
}

export function shareSentence(rows: InsightRow[]): Segment[] {
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  if (total === 0 || rows.length === 0) return [];
  if (rows.length === 1) return [plain("All "), em(rows[0].label), plain(".")];
  const share = Math.round((rows[0].count / total) * 100);
  return [
    em(rows[0].label),
    plain(" for "),
    em(`${share}%`),
    plain(", then "),
    em(rows[1].label),
    plain("."),
  ];
}

/**
 * How large a typeset term is drawn, in five steps of its share of the leader.
 * Steps rather than a continuous size, so a test can read the class.
 */
export function termSize(count: number, max: number): string {
  const share = count / Math.max(max, 1);
  if (share >= 0.8) return "text-4xl";
  if (share >= 0.5) return "text-3xl";
  if (share >= 0.3) return "text-2xl";
  if (share >= 0.15) return "text-xl";
  return "text-lg";
}

/** Whether a key reads as one proportion bar rather than a list of terms. */
export function readsAsShares(rows: InsightRow[]): boolean {
  return rows.length >= 2 && rows.length <= 6;
}
