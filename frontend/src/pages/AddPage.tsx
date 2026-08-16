import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import type { ItemType } from "@/api/library";
import { getItemTypes } from "@/api/library";
import { Button } from "@/components/ui/button";
import { AddForm } from "@/features/add/AddForm";
import { domainsFrom, labelFor } from "@/features/library/labels";

/**
 * Manual entry: the thing no provider has.
 *
 * Searching moved to `/` in Sprint 029, so this screen is what is left of the old add
 * page — the full validated form for something you are typing in yourself, reached
 * deliberately from *None of these — enter manually* or as a deep link. It is not a
 * compromise that it stayed a route: moving the form inline as well is a second
 * sprint's worth of work, and lazy-loading means keeping it costs nothing.
 *
 * **It has no domain chooser, and that is not an omission.** `LibraryService.add`
 * types a manual item as `DEFAULT_DOMAIN.item_type` regardless of what the client
 * sends (DEC-067 row 6). The old screen offered the choice anyway, which meant
 * picking Records here showed a record's statuses and fields and then wrote a book.
 * Until the manual path can honour a domain, naming one would be a promise this
 * screen cannot keep, so it names the one it actually makes.
 */
export function AddPage() {
  const [itemTypes, setItemTypes] = useState<ItemType[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    void getItemTypes()
      .then((types) => setItemTypes(domainsFrom(types)))
      .catch(() => undefined);
  }, []);

  // The registry publishes its domains in the order the backend declares them, and
  // the backend's default is the first of those. One place, one assumption, named.
  const itemType = itemTypes[0]?.id ?? "";
  const label = labelFor(itemType, itemTypes);

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <Button variant="ghost" className="px-0" onClick={() => navigate("/")}>
        ← Library
      </Button>
      <h1 className="mt-6 text-4xl font-semibold">Enter by hand</h1>
      <p className="mt-2 text-muted-foreground">
        For something no provider lists. To add from a provider, search from the
        library.
      </p>
      <div className="mt-8">
        <AddForm
          itemType={itemType}
          itemTypes={itemTypes}
          candidate={null}
          manual
          onAdded={(entryId, alreadyExists) => {
            if (alreadyExists) {
              toast("Already in your library", {
                description: "Opened the entry you already have.",
              });
              navigate(`/books/${entryId}`);
              return;
            }
            toast.success(`${label} added`);
            // The destination highlights the new row. This travels as router
            // state rather than sessionStorage so a reload does not resurrect a
            // stale highlight, and so the handoff is visible in the navigation
            // itself.
            navigate("/", { state: { newEntryId: entryId } });
          }}
          onOpenExisting={(entryId) => navigate(`/books/${entryId}`)}
        />
      </div>
    </main>
  );
}
