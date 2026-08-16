import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { searchCandidates, type SearchCandidate } from "@/api/add";
import type { ItemType } from "@/api/library";
import { getItemTypes } from "@/api/library";
import { ProviderHealthNotice } from "@/components/ProviderHealthNotice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AddForm } from "@/features/add/AddForm";
import { ResultsGrid } from "@/features/add/ResultsGrid";
import { domainsFrom, labelFor } from "@/features/library/labels";
import { cn } from "@/lib/utils";

export function AddPage() {
  const [query, setQuery] = useState("");
  // Which domain is being searched. Not a filter over one result set: it decides
  // which providers are asked at all (DEC-052 seam 6).
  const [itemType, setItemType] = useState("book");
  const [itemTypes, setItemTypes] = useState<ItemType[]>([]);
  const [results, setResults] = useState<SearchCandidate[]>([]);
  const [selected, setSelected] = useState<SearchCandidate | null>(null);
  const [manual, setManual] = useState(false);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  const [pending, setPending] = useState(false);
  const searchRequestId = useRef(0);
  const navigate = useNavigate();
  useEffect(() => {
    if (query.trim().length < 2) return setResults([]);
    // Two guards, and both earn their place. The request id decides which
    // response is allowed to land, so a slow first search can never overwrite a
    // fast second one. The abort actually stops the first one: provider search
    // takes about five seconds, so without it a few keystrokes leave several
    // multi-second requests running against a rate-limited free API for results
    // that will be thrown away (technical spec section 8).
    const requestId = ++searchRequestId.current;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setPending(true);
      setError("");
      void searchCandidates(query, itemType, controller.signal)
        .then((value) => {
          if (searchRequestId.current !== requestId) return;
          setResults(value.items);
          setWarning(value.warning ?? "");
        })
        .catch((e: Error) => {
          // An abort is this effect's own cleanup, not a failure the reader
          // needs to be told about.
          if (e.name === "AbortError") return;
          if (searchRequestId.current !== requestId) return;
          setError(e.message);
          setWarning("You can still enter it by hand.");
        })
        .finally(() => {
          if (searchRequestId.current !== requestId) return;
          setPending(false);
        });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, itemType]);
  // The domains come from the server, so this screen never enumerates them itself.
  // Through `domainsFrom`, because an odd-shaped or failed registry response must
  // leave a usable screen rather than crash the form that reads it.
  useEffect(() => {
    void getItemTypes()
      .then((types) => setItemTypes(domainsFrom(types)))
      .catch(() => undefined);
  }, []);

  const editing = manual || selected;
  const label = labelFor(itemType, itemTypes);
  const searchLabel = `Search ${label.toLowerCase()}s`;
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <Button variant="ghost" className="px-0" onClick={() => navigate("/")}>
        ← Library
      </Button>
      <h1 className="mt-6 text-4xl font-semibold">Add to your library</h1>
      {!editing && (
        <>
          {itemTypes.length > 1 && (
            <div
              role="radiogroup"
              aria-label="What are you adding?"
              className="mt-6 inline-flex rounded-full bg-surface p-1"
            >
              {itemTypes.map((choice) => (
                <button
                  key={choice.id}
                  type="button"
                  role="radio"
                  aria-checked={itemType === choice.id}
                  className={cn(
                    "rounded-full px-5 py-2 text-sm font-medium transition-colors",
                    itemType === choice.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  onClick={() => {
                    setItemType(choice.id);
                    setResults([]);
                    setManual(false);
                  }}
                >
                  {choice.label}
                </button>
              ))}
            </div>
          )}
          <label className="mt-4 block">
            <span className="sr-only">{searchLabel}</span>
            <Input
              autoFocus
              role="searchbox"
              aria-label={searchLabel}
              className="h-12 rounded-full bg-surface px-5"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Title, creator, ISBN or link"
            />
          </label>
          <ProviderHealthNotice />
          {pending && <p role="status">Searching metadata providers…</p>}
          {error && <p role="alert">{error}</p>}
          {warning && <p role="status">{warning}</p>}
          <ResultsGrid
            results={results}
            label="Search results"
            onSelect={setSelected}
            onManual={() => setManual(true)}
          />
        </>
      )}
      {editing && (
        <div className="mt-8">
          <AddForm
            itemType={itemType}
            itemTypes={itemTypes}
            candidate={manual ? null : selected}
            manual={manual}
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
