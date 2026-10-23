import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/keys";
import { patchEntry, type LibraryEntry } from "@/api/library";
import {
  getEntryLoans,
  getLocations,
  lendEntry,
  updateLoan,
} from "@/api/loans";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { localDay } from "@/features/progress/outline";

import { howLong, readableDay } from "./house";

/** The property row's frame, as the detail page draws its other rows. */
function Row({
  name,
  label,
  icon,
  children,
  below,
}: {
  name: string;
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  below?: React.ReactNode;
}) {
  return (
    <div
      data-fact={name}
      className="group -mx-2 grid grid-cols-[9.5rem_1fr] items-center gap-x-3 rounded-md px-2 py-1.5 sm:grid-cols-[11rem_1fr]"
    >
      <dt className="flex items-center gap-2 text-sm text-muted-foreground [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0">
        {icon}
        {label}
      </dt>
      <dd className="flex min-w-0 items-center justify-between gap-2">
        {children}
      </dd>
      {below}
    </div>
  );
}

const quietButton =
  "ml-auto shrink-0 rounded px-1.5 text-xs text-muted-foreground focus-ring hover:text-foreground";

function useRefresh(entryId: number) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.entry(entryId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    void queryClient.invalidateQueries({ queryKey: queryKeys.loans });
    void queryClient.invalidateQueries({ queryKey: queryKeys.locations });
  };
}

/**
 * Where it is kept (Sprint 111, DEC-176): one line of the owner's words, with the
 * places already used offered back so "Hall" stays "Hall" and not "hall".
 */
export function LocationRow({
  entry,
  icon,
}: {
  entry: LibraryEntry;
  icon: React.ReactNode;
}) {
  const listId = useId();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(entry.location ?? "");
  const refresh = useRefresh(entry.id);
  const places = useQuery({
    queryKey: queryKeys.locations,
    queryFn: ({ signal }) => getLocations(signal),
    enabled: editing,
  });
  const save = useMutation({
    mutationFn: (location: string) =>
      patchEntry(entry.id, { location: location.trim() || null }),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(draft);
  };
  return (
    <Row name="location" label="Where" icon={icon}>
      {editing ? (
        <form onSubmit={submit} className="flex min-w-0 flex-1 gap-2">
          <Input
            autoFocus
            aria-label="Where it is"
            list={listId}
            value={draft}
            maxLength={120}
            placeholder="Living room, shelf 2"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.stopPropagation();
                setEditing(false);
              }
            }}
            className="h-9 min-w-0 flex-1"
          />
          <datalist id={listId}>
            {(Array.isArray(places.data) ? places.data : []).map((place) => (
              <option key={place.location} value={place.location} />
            ))}
          </datalist>
          <Button type="submit" size="sm" disabled={save.isPending}>
            Save
          </Button>
        </form>
      ) : (
        <>
          <span className="min-w-0 truncate">{entry.location ?? "—"}</span>
          <button
            type="button"
            aria-label="Change where it is"
            onClick={() => {
              setDraft(entry.location ?? "");
              setEditing(true);
            }}
            className={`${quietButton} after:content-['Change']`}
          />
        </>
      )}
    </Row>
  );
}

/**
 * Who has it (Sprint 111, DEC-176): lent in two taps, back in one, and who had it
 * before listed under the row. Today is the reader's own day, as every date here.
 */
export function LoanRow({
  entry,
  icon,
}: {
  entry: LibraryEntry;
  icon: React.ReactNode;
}) {
  const listId = useId();
  const [lending, setLending] = useState(false);
  const [person, setPerson] = useState("");
  const [lentOn, setLentOn] = useState(() => localDay(new Date()));
  const refresh = useRefresh(entry.id);
  const history = useQuery({
    queryKey: queryKeys.entryLoans(entry.id),
    queryFn: ({ signal }) => getEntryLoans(entry.id, signal),
  });
  const lend = useMutation({
    mutationFn: () =>
      lendEntry(entry.id, { person: person.trim(), lent_on: lentOn }),
    onSuccess: () => {
      setLending(false);
      setPerson("");
      refresh();
    },
  });
  const back = useMutation({
    mutationFn: (loanId: number) =>
      updateLoan(loanId, { returned_on: localDay(new Date()) }),
    onSuccess: refresh,
  });
  const open = entry.loan;
  // Defensive, as the registry is: a history that failed to arrive draws nothing.
  const loans = Array.isArray(history.data) ? history.data : [];
  const past = loans.filter((loan) => loan.returned_on);
  const people = Array.from(new Set(loans.map((loan) => loan.person)));
  const failure = lend.error ?? back.error;
  return (
    <Row
      name="loan"
      label="Lent"
      icon={icon}
      below={
        (lending || past.length > 0 || failure) && (
          <dd className="col-span-2 space-y-2 pb-2 pt-2 text-sm">
            {lending && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (person.trim()) lend.mutate();
                }}
                className="flex flex-wrap items-center gap-2"
              >
                <Input
                  autoFocus
                  aria-label="Who has it"
                  list={listId}
                  value={person}
                  maxLength={120}
                  placeholder="Who"
                  onChange={(event) => setPerson(event.target.value)}
                  className="h-9 w-40"
                />
                <datalist id={listId}>
                  {people.map((name) => (
                    <option key={name} value={name} />
                  ))}
                </datalist>
                <Input
                  type="date"
                  aria-label="Lent on"
                  value={lentOn}
                  onChange={(event) => setLentOn(event.target.value)}
                  className="h-9 w-40"
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={!person.trim() || lend.isPending}
                >
                  Lend
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setLending(false)}
                >
                  Cancel
                </Button>
              </form>
            )}
            {failure && (
              <p role="alert" className="text-destructive">
                {failure.message}
              </p>
            )}
            {past.length > 0 && (
              <p className="text-muted-foreground">
                Before:{" "}
                {past
                  .map(
                    (loan) =>
                      `${loan.person}, ${readableDay(loan.lent_on)} to ${readableDay(loan.returned_on!)}`,
                  )
                  .join(" · ")}
              </p>
            )}
          </dd>
        )
      }
    >
      {open ? (
        <>
          <span className="min-w-0">
            To <span className="font-medium">{open.person}</span>{" "}
            <span className="text-muted-foreground">
              · {readableDay(open.lent_on)} ·{" "}
              {howLong(open.lent_on, new Date())}
            </span>
          </span>
          <span className="ml-auto flex shrink-0 items-center gap-2">
            <Link to="/lent" className={quietButton}>
              All lent
            </Link>
            <button
              type="button"
              onClick={() => back.mutate(open.id)}
              disabled={back.isPending}
              className="rounded-full bg-primary/15 px-3 py-1 text-xs font-medium text-primary focus-ring hover:bg-primary/25"
            >
              It's back
            </button>
          </span>
        </>
      ) : (
        <>
          <span className="text-muted-foreground">—</span>
          {!lending && (
            <button
              type="button"
              onClick={() => {
                setLentOn(localDay(new Date()));
                setLending(true);
              }}
              className={quietButton}
            >
              Lend…
            </button>
          )}
        </>
      )}
    </Row>
  );
}
