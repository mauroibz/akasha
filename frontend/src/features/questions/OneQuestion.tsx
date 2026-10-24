import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { queryKeys } from "@/api/keys";
import {
  patchEntry,
  type EntryFormat,
  type EntryPatch,
  type ItemType,
  type LibraryEntry,
} from "@/api/library";
import { getLocations } from "@/api/loans";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { localDay } from "@/features/progress/outline";

import { questionsFor, type Question } from "./questions";

const asked: Record<Question, string> = {
  date_finished: "When did you finish it?",
  formats: "How do you have it?",
  location: "Where is it?",
  date_started: "When did you start it?",
};

const chip =
  "min-h-11 rounded-full border border-border bg-surface px-4 text-sm font-medium transition-colors hover:bg-accent focus-ring";

/**
 * One thing to add (Sprint 124, DEC-179, mockup 1A): the personal region shows what
 * it has, and below it one question about the most useful gap, answered in a tap or
 * a date. *I don't remember* is kept on the entry so it is never asked again; *Skip*
 * moves on for this visit only.
 */
export function OneQuestion({
  entry,
  types,
}: {
  entry: LibraryEntry;
  types: ItemType[] | undefined;
}) {
  const [skipped, setSkipped] = useState<Question[]>([]);
  const questions = questionsFor(entry, types);
  const current = questions.find((question) => !skipped.includes(question));
  if (!current) return null;
  return (
    <Card
      // A fresh card per question, so a draft never carries over.
      key={current}
      entry={entry}
      types={types}
      question={current}
      position={`${questions.indexOf(current) + 1} of ${questions.length}`}
      onSkip={() => setSkipped((rows) => [...rows, current])}
    />
  );
}

function Card({
  entry,
  types,
  question,
  position,
  onSkip,
}: {
  entry: LibraryEntry;
  types: ItemType[] | undefined;
  question: Question;
  position: string;
  onSkip: () => void;
}) {
  const queryClient = useQueryClient();
  // Empty, never today: a book finished years ago saved as today is worse than
  // no date at all.
  const [draft, setDraft] = useState("");
  const places = useQuery({
    queryKey: queryKeys.locations,
    queryFn: ({ signal }) => getLocations(signal),
    enabled: question === "location",
  });
  const formats =
    (Array.isArray(types) ? types : []).find(
      (row) => row.id === entry.item.type,
    )?.formats ?? [];
  const save = useMutation({
    mutationFn: (changes: EntryPatch) => patchEntry(entry.id, changes),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.entry(entry.id), saved);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.entry(entry.id),
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      if (question === "location")
        void queryClient.invalidateQueries({ queryKey: queryKeys.locations });
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = draft.trim();
    if (value) save.mutate({ [question]: value });
  };
  const known = Array.isArray(places.data) ? places.data.slice(0, 4) : [];
  const headingId = `question-${question}`;

  return (
    <section
      aria-labelledby={headingId}
      data-question={question}
      className="mt-4 rounded-xl bg-primary/10 p-4"
    >
      <p className="flex justify-between text-xs font-semibold uppercase tracking-[0.12em] text-primary">
        One thing to add
        <span className="font-normal normal-case tracking-normal text-muted-foreground">
          {position}
        </span>
      </p>
      <h3
        id={headingId}
        className="mt-1.5 font-display text-xl font-medium leading-tight"
      >
        {asked[question]}
      </h3>
      <form
        onSubmit={submit}
        className="mt-3 flex flex-wrap items-center gap-2"
      >
        {question === "formats" &&
          formats.map((format) => (
            <button
              key={format.value}
              type="button"
              disabled={save.isPending}
              onClick={() =>
                save.mutate({ formats: [format.value as EntryFormat] })
              }
              className={chip}
            >
              {format.label}
            </button>
          ))}
        {question === "location" && (
          <>
            {known.map((place) => (
              <button
                key={place.location}
                type="button"
                disabled={save.isPending}
                onClick={() => save.mutate({ location: place.location })}
                className={chip}
              >
                {place.location}
              </button>
            ))}
            <Input
              aria-label="Where it is"
              value={draft}
              maxLength={120}
              placeholder={
                known.length ? "Somewhere else" : "Living room, shelf 2"
              }
              onChange={(event) => setDraft(event.target.value)}
              className="h-11 w-44 bg-surface"
            />
          </>
        )}
        {(question === "date_finished" || question === "date_started") && (
          <Input
            type="date"
            aria-label="Date"
            aria-describedby={headingId}
            value={draft}
            max={localDay(new Date())}
            onChange={(event) => setDraft(event.target.value)}
            className="h-11 w-auto bg-surface"
          />
        )}
        {question !== "formats" && (
          <Button
            type="submit"
            className="rounded-full px-5"
            disabled={!draft.trim() || save.isPending}
          >
            Save
          </Button>
        )}
      </form>
      <div className="mt-2 flex flex-wrap gap-x-4">
        <button
          type="button"
          disabled={save.isPending}
          onClick={() =>
            save.mutate({
              unknown_fields: [...(entry.unknown_fields ?? []), question],
            })
          }
          className="min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
        >
          I don't remember
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
        >
          Skip
        </button>
      </div>
      {save.error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {save.error.message}
        </p>
      )}
    </section>
  );
}
