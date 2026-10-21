import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  ArrowRight,
  BookPlus,
  ChartBar,
  Download,
  Inbox,
  LibraryBig,
  Bookmark,
  Moon,
  Plus,
  Search,
  Settings,
  Sun,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import {
  createEntry,
  looksResolvable,
  NearMatchError,
  searchCandidates,
  type SearchCandidate,
} from "@/api/add";
import { queryKeys } from "@/api/keys";
import { searchLibrary } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useItemTypes } from "@/features/library/useItemTypes";
import { readThemeChoice, resolveTheme, saveThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { navigateWithTransition } from "@/lib/viewTransition";

interface Action {
  id: string;
  label: string;
  words: string;
  icon: React.ReactNode;
  run: () => void;
}

function useDebounced<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

const ITEM =
  "flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm aria-selected:bg-accent data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50";
const HEADING =
  "[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground";

/**
 * The command bar (Sprint 094, proposal §4.1): one place that takes anything you can
 * type. It finds in your library (ranked by the server), searches the web for the
 * chosen domain with an explicit Add, resolves a pasted link or ISBN to one card,
 * and goes places. Filtering is off in cmdk because every result list is already
 * the server's answer to exactly what was typed.
 */
export function CommandBar({
  open,
  onOpenChange,
  initialQuery,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialQuery: string;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const itemTypes = useItemTypes();
  const domains = Array.isArray(itemTypes.data) ? itemTypes.data : [];
  const [query, setQuery] = useState(initialQuery);
  const [domain, setDomain] = useState<string | null>(null);
  const [added, setAdded] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!open) return;
    setQuery(initialQuery);
    setAdded({});
    // The library's chosen domain is the likeliest one to add into.
    setDomain(new URLSearchParams(location.search).get("type"));
    // Only when the bar opens: typing must not reset the domain.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialQuery]);

  const chosenDomain = domain ?? domains[0]?.id ?? "book";
  const typed = useDebounced(query.trim(), 220);
  const resolvable = looksResolvable(typed);

  const library = useQuery({
    queryKey: ["command", "library", typed],
    queryFn: ({ signal }) => searchLibrary(typed, signal),
    enabled: open && typed.length >= 2 && !resolvable,
    staleTime: 30_000,
  });
  const web = useQuery({
    queryKey: ["command", "web", resolvable ? "resolve" : chosenDomain, typed],
    queryFn: ({ signal }) => searchCandidates(typed, chosenDomain, signal),
    enabled: open && (resolvable || typed.length >= 3),
    staleTime: 5 * 60_000,
    retry: false,
  });

  const close = () => onOpenChange(false);
  const go = (to: string) => {
    close();
    navigateWithTransition(navigate, to);
  };

  const add = useMutation({
    mutationFn: ({
      candidate,
      confirm,
    }: {
      candidate: SearchCandidate;
      confirm?: boolean;
    }) =>
      createEntry({
        source: candidate.source,
        source_id: candidate.source_id,
        source_refs: candidate.source_refs,
        shelf_ids: [],
        confirm_near_match: confirm,
      }),
    onSuccess: (result, { candidate }) => {
      const key = `${candidate.source}:${candidate.source_id}`;
      setAdded((current) => ({ ...current, [key]: result.entry.id }));
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.triage.all });
      const open = {
        label: "Open",
        onClick: () => navigate(`/books/${result.entry.id}`),
      };
      if (result.already_exists)
        toast(`${candidate.title} is already in your library`, {
          action: open,
        });
      else toast.success(`Added ${candidate.title}`, { action: open });
    },
    onError: (error, { candidate }) => {
      if (error instanceof NearMatchError) {
        toast(`A similar edition of ${candidate.title} is already here`, {
          action: {
            label: "Add anyway",
            onClick: () => add.mutate({ candidate, confirm: true }),
          },
        });
        return;
      }
      toast.error(
        error instanceof Error ? error.message : "That could not be added",
      );
    },
  });

  const actions = useMemo<Action[]>(() => {
    const theme = resolveTheme(readThemeChoice());
    return [
      {
        id: "library",
        label: "Go to Library",
        words: "library home books",
        icon: <LibraryBig />,
        run: () => go("/"),
      },
      {
        id: "inbox",
        label: "Go to Inbox",
        words: "inbox triage unsorted sort",
        icon: <Inbox />,
        run: () => go("/import?tab=triage"),
      },
      {
        id: "shelves",
        label: "Go to Shelves",
        words: "shelves shelf lists",
        icon: <Bookmark />,
        run: () => go("/shelves"),
      },
      {
        id: "insights",
        label: "Go to Insights",
        words: "insights stats statistics charts",
        icon: <ChartBar />,
        run: () => go("/insights"),
      },
      {
        id: "import",
        label: "Import a file…",
        words: "import upload goodreads csv calibre file data",
        icon: <Upload />,
        run: () => go("/import"),
      },
      {
        id: "export",
        label: "Export your library…",
        words: "export download backup data",
        icon: <Download />,
        run: () => go("/import?tab=export"),
      },
      {
        id: "manual",
        label: "Add by hand…",
        words: "add manual new form create",
        icon: <BookPlus />,
        run: () => go("/add"),
      },
      {
        id: "settings",
        label: "Settings",
        words: "settings preferences appearance",
        icon: <Settings />,
        run: () => go("/settings"),
      },
      {
        id: "theme",
        label: theme === "ink" ? "Switch to Paper" : "Switch to Ink",
        words: "theme dark light paper ink appearance",
        icon: theme === "ink" ? <Sun /> : <Moon />,
        run: () => {
          saveThemeChoice(theme === "ink" ? "paper" : "ink");
          close();
        },
      },
    ];
    // `go` and `close` are stable enough for a menu rebuilt on each open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const words = query.trim().toLowerCase();
  const shownActions = words
    ? actions.filter((action) =>
        `${action.label} ${action.words}`.toLowerCase().includes(words),
      )
    : actions;
  // While the typing has not settled, results on screen answer the previous text:
  // hide them, so Enter acts on what was typed rather than on what was there.
  const settling = query.trim() !== typed;
  const libraryRows = settling ? [] : (library.data ?? []);
  const webRows = settling ? [] : (web.data?.items ?? []);
  const domainLabel =
    domains.find((item) => item.id === chosenDomain)?.label ?? "Books";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 overflow-hidden p-0 sm:top-[12%] sm:max-w-2xl sm:translate-y-0 sm:p-0">
        <DialogTitle className="sr-only">Search or add</DialogTitle>
        <DialogDescription className="sr-only">
          Find something in your library, search the web to add it, paste a
          link, or go to a page.
        </DialogDescription>
        <CommandPrimitive
          // cmdk names its input from this label (its own aria-labelledby).
          label="Search or add"
          shouldFilter={false}
          loop
          className={cn("flex flex-col bg-popover", HEADING)}
        >
          <div className="flex items-center gap-2 border-b border-border pl-4 pr-12">
            <Search
              className="h-5 w-5 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
            <CommandPrimitive.Input
              value={query}
              onValueChange={setQuery}
              autoFocus
              placeholder="Find in your library, search the web, or paste a link"
              className="h-14 w-full bg-transparent text-base outline-none placeholder:text-muted-foreground"
            />
          </div>
          {!resolvable && domains.length > 1 && typed.length >= 3 && (
            <div
              className="flex gap-1.5 overflow-x-auto border-b border-border px-4 py-2"
              role="group"
              aria-label="Search the web for"
            >
              {domains.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={item.id === chosenDomain}
                  onClick={() => setDomain(item.id)}
                  className="shrink-0 rounded-full px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-ring aria-pressed:bg-primary/15 aria-pressed:text-primary"
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
          <CommandPrimitive.List className="max-h-[min(60dvh,520px)] overflow-y-auto px-2 pb-2">
            {libraryRows.length > 0 && (
              <CommandPrimitive.Group heading="In your library">
                {libraryRows.map((entry) => (
                  <CommandPrimitive.Item
                    key={`entry-${entry.id}`}
                    value={`entry-${entry.id}`}
                    onSelect={() => go(`/books/${entry.id}`)}
                    className={ITEM}
                  >
                    <CoverImage
                      src={entry.item.cover_url}
                      alt=""
                      className="h-12 w-8 shrink-0 rounded-sm object-cover"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {entry.item.title}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {entry.item.creator ?? ""}
                      </span>
                    </span>
                    <ArrowRight
                      className="h-4 w-4 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </CommandPrimitive.Item>
                ))}
              </CommandPrimitive.Group>
            )}
            {!settling && (resolvable || typed.length >= 3) && (
              <CommandPrimitive.Group
                heading={
                  resolvable ? "From that link" : `On the web · ${domainLabel}`
                }
              >
                {web.isFetching && webRows.length === 0 && (
                  <p
                    className="px-2 py-3 text-sm text-muted-foreground"
                    role="status"
                  >
                    Searching…
                  </p>
                )}
                {web.isError && (
                  <p
                    className="px-2 py-3 text-sm text-muted-foreground"
                    role="status"
                  >
                    {web.error instanceof Error
                      ? web.error.message
                      : "The web search did not answer."}
                  </p>
                )}
                {!web.isFetching &&
                  !web.isError &&
                  web.data &&
                  webRows.length === 0 && (
                    <p
                      className="px-2 py-3 text-sm text-muted-foreground"
                      role="status"
                    >
                      Nothing found on the web for that.
                    </p>
                  )}
                {webRows.slice(0, 8).map((candidate) => {
                  const key = `${candidate.source}:${candidate.source_id}`;
                  const addedId = added[key];
                  return (
                    <CommandPrimitive.Item
                      key={`web-${key}`}
                      value={`web-${key}`}
                      onSelect={() =>
                        addedId
                          ? go(`/books/${addedId}`)
                          : add.mutate({ candidate })
                      }
                      className={ITEM}
                    >
                      <CoverImage
                        src={candidate.cover_url}
                        alt=""
                        className="h-12 w-8 shrink-0 rounded-sm object-cover"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">
                          {candidate.title}
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {[
                            candidate.credit ?? candidate.creators.join(", "),
                            candidate.year,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </span>
                      <span
                        className={cn(
                          "inline-flex h-8 shrink-0 items-center gap-1 rounded-full px-3 text-xs font-medium",
                          addedId
                            ? "text-muted-foreground"
                            : "bg-primary text-primary-foreground",
                        )}
                      >
                        {addedId ? (
                          "Added · Open"
                        ) : (
                          <>
                            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                            Add
                          </>
                        )}
                      </span>
                    </CommandPrimitive.Item>
                  );
                })}
              </CommandPrimitive.Group>
            )}
            {shownActions.length > 0 && (
              <CommandPrimitive.Group heading="Go to and do">
                {shownActions.map((action) => (
                  <CommandPrimitive.Item
                    key={action.id}
                    value={`action-${action.id}`}
                    onSelect={action.run}
                    className={cn(
                      ITEM,
                      "[&_svg]:h-4 [&_svg]:w-4 [&_svg]:text-muted-foreground",
                    )}
                  >
                    {action.icon}
                    {action.label}
                  </CommandPrimitive.Item>
                ))}
              </CommandPrimitive.Group>
            )}
          </CommandPrimitive.List>
        </CommandPrimitive>
      </DialogContent>
    </Dialog>
  );
}
