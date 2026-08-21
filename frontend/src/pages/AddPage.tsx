import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import type { ItemType } from "@/api/library";
import { getItemTypes } from "@/api/library";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
 * The domain chooser is authoritative: it changes both the fields rendered from the
 * registry and the domain named in the write. The server validates the same field
 * declaration before storing anything (DEC-067 row 6).
 */
export function AddPage() {
  const [itemTypes, setItemTypes] = useState<ItemType[]>([]);
  const [itemType, setItemType] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    void getItemTypes()
      .then((types) => {
        const domains = domainsFrom(types);
        setItemTypes(domains);
        setItemType((current) => current || domains[0]?.id || "");
      })
      .catch(() => undefined);
  }, []);

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
      {itemTypes.length > 0 && (
        <div className="mt-7 max-w-xs">
          <Label htmlFor="manual-domain">Domain</Label>
          <Select value={itemType} onValueChange={setItemType}>
            <SelectTrigger
              id="manual-domain"
              aria-label="Domain"
              className="mt-1 h-11"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {itemTypes.map((type) => (
                <SelectItem key={type.id} value={type.id}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {itemType && (
        <div className="mt-8">
          <AddForm
            key={itemType}
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
      )}
    </main>
  );
}
