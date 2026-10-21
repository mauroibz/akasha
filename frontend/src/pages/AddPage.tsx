import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import type { ImporterDefinition } from "@/api/imports";
import { getImporters } from "@/api/imports";
import type { ItemType } from "@/api/library";
import { getItemTypes } from "@/api/library";
import { PageHeader } from "@/components/PageHeader";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AddForm } from "@/features/add/AddForm";
import { ExportPicker } from "@/features/import/ExportPicker";
import { handFiles } from "@/features/import/handoff";
import { domainsFrom, labelFor } from "@/features/library/labels";

/**
 * Adding something without a provider search: files dropped in, or typed by hand.
 *
 * The drop zones come first (Sprint 086): every connector whose input declares
 * `quick_add` gets one, rendered from that declaration and never by name. A drop
 * hands the files to the import screen on that connector, which previews them at
 * once — Add is the door, Import is still the one place a batch is reviewed,
 * committed and undone.
 *
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
  const [droppable, setDroppable] = useState<ImporterDefinition[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    void getImporters()
      .then((importers) =>
        setDroppable(
          Array.isArray(importers)
            ? // A multi-file input only: one motion, several files, no
              // mapping or choice to make before the preview.
              importers.filter(
                (importer) =>
                  importer.input.quick_add && importer.input.kind === "export",
              )
            : [],
        ),
      )
      .catch(() => undefined);
  }, []);

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
      <PageHeader
        back
        title="Add"
        lede="Drop files in, or enter something no provider lists. To add from a provider, press ⌘K or use Search or add: it finds titles and reads links."
      />
      {droppable.map((importer) => (
        <section
          key={importer.id}
          aria-labelledby={`${importer.id}-quick-add`}
          className="mt-7"
        >
          <h2 id={`${importer.id}-quick-add`} className="text-lg font-semibold">
            {importer.label}
          </h2>
          {importer.input.help && (
            <p className="mt-1 text-sm text-muted-foreground">
              {importer.input.help}
            </p>
          )}
          <div className="mt-3">
            <ExportPicker
              importerId={importer.id}
              spec={importer.input}
              inputId={`${importer.id}-quick-add-files`}
              files={[]}
              onFiles={(files) => {
                if (files.length === 0) return;
                handFiles(importer.id, files);
                navigate(`/import?tab=${importer.id}`);
              }}
            />
          </div>
        </section>
      ))}
      <h2 className="mt-10 text-lg font-semibold">Enter by hand</h2>
      {itemTypes.length > 0 && (
        <div className="mt-4 max-w-xs">
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
