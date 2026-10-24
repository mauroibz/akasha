import { modalScore, spelled, type Segment } from "@/features/insights/prose";
import { scoreArticle } from "@/features/rescore/rescore";

/**
 * The year in review, read back as sentences (Sprint 120, DEC-178), in the shapes
 * Insights writes (Sprint 102). Segments, so the page sets the figures apart; nouns
 * come in as a function, never chosen here.
 */

const em = (text: string): Segment => ({ text, em: true });
const plain = (text: string): Segment => ({ text });
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

function listed(parts: string[]): string {
  if (parts.length < 2) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

export function leadSentence(params: {
  counts: Record<string, number>;
  finished: number;
  scores: number[];
  leader: { name: string; count: number } | null;
  noun: (type: string, count: number) => string;
}): Segment[] {
  const { counts, finished, scores, leader, noun } = params;
  const kinds = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const parts: Segment[] =
    kinds.length === 1
      ? [plain("You finished "), em(noun(kinds[0][0], kinds[0][1])), plain(".")]
      : [
          plain("You finished "),
          em(`${finished.toLocaleString()} things`),
          plain(
            `: ${listed(kinds.map(([type, count]) => noun(type, count)))}.`,
          ),
        ];
  const rated = scores.reduce((sum, count) => sum + count, 0);
  const modal = modalScore(scores);
  if (modal !== null && rated >= 5) {
    if (modal >= 8)
      parts.push(plain(" You rated "), em("generously"), plain("."));
    else if (modal <= 5)
      parts.push(plain(" You rated "), em("hard"), plain("."));
  }
  if (leader)
    parts.push(plain(" You returned most to "), em(leader.name), plain("."));
  return parts;
}

export function bestSentence(
  best: Array<{ title: string; score: number; month: string }>,
): Segment[] | null {
  const [top, ...rest] = best;
  if (!top) return null;
  const [article, value] = scoreArticle(top.score).split(" ");
  const parts: Segment[] = [
    plain(`Your highest score was ${article} `),
    em(value),
    plain(", for "),
    em(top.title),
    plain(`, in ${top.month}.`),
  ];
  const next = rest[0]?.score;
  const more = rest.filter((row) => row.score === next).length;
  if (next !== undefined && more > 0)
    parts.push(
      plain(
        ` ${capital(spelled(more))} more got ${scoreArticle(next).split(" ")[0]} `,
      ),
      em(String(next)),
      plain("."),
    );
  return parts;
}

export function monthsSentence(
  months: number[],
  name: (index: number) => string,
): Segment[] | null {
  const busiest = months.reduce(
    (best, count, index) => (count > months[best] ? index : best),
    0,
  );
  if (months[busiest] === 0) return null;
  const parts: Segment[] = [
    em(name(busiest)),
    plain(" was your busiest month, with "),
    em(spelled(months[busiest])),
    plain("."),
  ];
  const empty = months
    .map((count, index) => (count === 0 ? index : -1))
    .filter((index) => index >= 0);
  if (empty.length === 1)
    parts.push(plain(" "), em(name(empty[0])), plain(" had none."));
  else if (empty.length > 1)
    parts.push(plain(` ${capital(spelled(empty.length))} months had none.`));
  return parts;
}

export function changesSentence(
  changes: Array<{
    title: string;
    previous: number | null;
    score: number | null;
    reason: string | null;
  }>,
): Segment[] | null {
  const moved = changes.filter(
    (change) =>
      change.previous !== null &&
      change.score !== null &&
      change.previous !== change.score,
  );
  if (moved.length === 0) return null;
  const parts: Segment[] = [
    plain("You changed "),
    em(spelled(moved.length)),
    plain(moved.length === 1 ? " score." : " scores."),
  ];
  const said = moved
    .slice(0, 2)
    .map((change, index) => [
      plain(index === 0 ? " " : "; "),
      em(change.title),
      plain(
        ` went ${change.score! > change.previous! ? "up" : "down"} ${
          change.reason === "reread" ? "after a reread" : "with time"
        }`,
      ),
    ]);
  return [...parts, ...said.flat(), plain(".")];
}
