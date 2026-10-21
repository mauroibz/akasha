import { useQueries } from "@tanstack/react-query";

import { getItem } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { cn } from "@/lib/utils";

/**
 * What an ambiguous import row is (Sprint 096, proposal I4): each copy already in the
 * library, shown by its cover, title, creator and year, beside *a separate edition*.
 * It used to be a menu reading "Use existing item 42", a database id.
 */
export function AmbiguityChoice({
  recordId,
  title,
  candidates,
  value,
  onChange,
}: {
  recordId: number;
  title: string;
  candidates: number[];
  value: number | "new" | undefined;
  onChange: (value: number | "new") => void;
}) {
  const items = useQueries({
    queries: candidates.map((id) => ({
      queryKey: ["item", id],
      queryFn: () => getItem(id),
      staleTime: 60_000,
      retry: false,
    })),
  });
  const option = (
    key: string,
    checked: boolean,
    select: () => void,
    children: React.ReactNode,
  ) => (
    <label
      key={key}
      className={cn(
        "flex min-h-14 cursor-pointer items-center gap-3 rounded-lg border p-2 pr-3 transition-colors focus-within:ring-2 focus-within:ring-primary",
        checked
          ? "border-primary bg-primary/10"
          : "border-border hover:bg-muted/60",
      )}
    >
      <input
        type="radio"
        name={`choice-${recordId}`}
        checked={checked}
        onChange={select}
        className="sr-only"
      />
      {children}
    </label>
  );
  return (
    <fieldset className="mt-3">
      <legend className="mb-2 text-sm text-muted-foreground">
        Is this a copy you already have?
      </legend>
      <div
        role="radiogroup"
        aria-label={`Choice for ${title}`}
        className="grid gap-2 sm:grid-cols-2"
      >
        {candidates.map((id, index) => {
          const item = items[index]?.data;
          return option(
            String(id),
            value === id,
            () => onChange(id),
            <>
              <CoverImage
                src={item?.cover_url ?? null}
                alt=""
                className="h-14 w-10 shrink-0 rounded-sm object-cover"
              />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">
                  Your copy: {item?.title ?? title}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  {[item?.creator, item?.year].filter(Boolean).join(" · ") ||
                    "Already in your library"}
                </span>
              </span>
            </>,
          );
        })}
        {option(
          "new",
          value === "new",
          () => onChange("new"),
          <span className="min-w-0">
            <span className="block text-sm font-medium">
              A separate edition
            </span>
            <span className="block text-xs text-muted-foreground">
              Add it as its own item
            </span>
          </span>,
        )}
      </div>
    </fieldset>
  );
}
