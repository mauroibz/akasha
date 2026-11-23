import type { Home, ModuleSize } from "@/api/home";
import type { ItemType } from "@/api/library";

import { InsightShowcase } from "./InsightShowcase";
import { Lately } from "./Lately";
import { LibraryYear } from "./LibraryYear";
import { OnNow } from "./OnNow";
import { QuestionModule } from "./QuestionModule";
import { ShelfModule } from "./ShelfModule";
import { SuggestedModule } from "./SuggestedModule";
import { UpNext } from "./UpNext";
import { localDate } from "./year";

/**
 * One thing on the Library's front, drawn from a front payload (Sprint 150): the
 * same component whether it stands on the page or in Personalize's preview, which
 * is the point of a preview. Draws nothing when the payload has nothing for it.
 */
export function Showcase({
  moduleKey,
  size,
  label,
  data,
  types,
}: {
  moduleKey: string;
  size: ModuleSize;
  /** What the server calls a family member; a fixed one names itself. */
  label: string;
  data: Home;
  types: ItemType[] | undefined;
}) {
  if (moduleKey === "now")
    return data.now.length ? (
      <OnNow entries={data.now} types={types} size="L" />
    ) : null;
  if (moduleKey === "lately") return <Lately rows={data.lately ?? []} />;
  if (moduleKey === "next")
    return data.next.length ? (
      <UpNext
        picks={data.next}
        pile={data.greeting.pile}
        types={types}
        size={size}
      />
    ) : null;
  if (moduleKey === "question")
    return data.question ? (
      <QuestionModule question={data.question} types={types} />
    ) : null;
  if (moduleKey === "suggested")
    return data.suggested?.length ? (
      <SuggestedModule suggestions={data.suggested} types={types} size={size} />
    ) : null;
  if (moduleKey.startsWith("insight:"))
    return (
      <InsightShowcase moduleKey={moduleKey} label={label} types={types} />
    );
  const year = (data.library_years ?? []).find(
    (row) => `year:${row.item_type}` === moduleKey,
  );
  if (year)
    return (
      <LibraryYear
        year={year}
        types={types}
        size={size}
        today={localDate(data.greeting.today)}
      />
    );
  const shelf = (data.shelf_modules ?? []).find(
    (row) => `shelf:${row.id}` === moduleKey,
  );
  return shelf ? <ShelfModule shelf={shelf} size={size} /> : null;
}
