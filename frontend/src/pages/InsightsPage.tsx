import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { domainsFrom, insightKeyOptions } from "@/features/library/labels";
import { InsightsKeyPicker } from "@/features/library/InsightsKeyPicker";
import { InsightsRanking } from "@/features/library/InsightsRanking";
import { orderRows, type InsightSort } from "@/features/library/insights";
import { useInsights } from "@/features/library/useInsights";
import { useItemTypes } from "@/features/library/useItemTypes";

/**
 * Ask the library a question it already has the answer to — which authors you rate
 * highest, which bands you own most of — from the fields items already declare
 * (Sprint 065). Never crosses domains: DEC-052 and DEC-077 twice declined to create
 * the cross-domain creator identity that would need, and this feature exists to keep
 * it that way. A ranking row links into the filtered library, not to a new entity
 * screen of its own.
 */
export function InsightsPage() {
  const navigate = useNavigate();
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const itemTypes = useItemTypes();
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);

  const [type, setType] = useState("");
  const [key, setKey] = useState("");
  const [sort, setSort] = useState<InsightSort>("count");
  const [minRated, setMinRated] = useState(2);
  const [includeSuppressed, setIncludeSuppressed] = useState(false);

  // The registry loads after this component mounts, so the first domain and its
  // first groupable key are chosen once it arrives rather than assumed up front.
  useEffect(() => {
    if (type || domains.length === 0) return;
    setType(domains[0].id);
  }, [domains, type]);

  const selectedDomain = domains.find((domain) => domain.id === type);
  const keyOptions = useMemo(
    () => (selectedDomain ? insightKeyOptions(selectedDomain.fields) : []),
    [selectedDomain],
  );

  useEffect(() => {
    if (!selectedDomain) return;
    if (keyOptions.some((option) => option.name === key)) return;
    setKey(keyOptions[0]?.name ?? "");
  }, [selectedDomain, keyOptions, key]);

  const insights = useInsights({ type, key, includeSuppressed });

  // One response, read in the order the reader asked for. `unplaced` is what the
  // score order cannot rank -- kept and shown below a divider rather than dropped.
  const ranking = useMemo(
    () => orderRows(insights.data?.rows ?? [], sort, minRated),
    [insights.data, sort, minRated],
  );
  const nothingPlaceable =
    sort === "score" &&
    ranking.placed.length === 0 &&
    ranking.unplaced.length > 0;

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-8">
      <Button variant="ghost" className="px-0" onClick={() => navigate("/")}>
        ← Library
      </Button>
      <h1
        ref={headingRef}
        tabIndex={-1}
        className="mt-6 text-4xl font-semibold focus:outline-none"
      >
        Insights
      </h1>
      <p className="mt-2 text-muted-foreground">
        A ranking from what your library already declares — one domain at a
        time.
      </p>

      <section
        aria-label="Ranking controls"
        className="mt-6 flex flex-wrap items-center gap-3"
      >
        {domains.length > 1 && (
          <div
            role="radiogroup"
            aria-label="Choose a domain"
            className="inline-flex shrink-0 rounded-full bg-surface p-1"
          >
            {domains.map((choice) => (
              <button
                key={choice.id}
                type="button"
                role="radio"
                aria-checked={type === choice.id}
                className={`min-h-11 rounded-full px-5 py-2 text-sm font-medium transition-colors ${
                  type === choice.id
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                } focus-ring`}
                onClick={() => setType(choice.id)}
              >
                {choice.label}
              </button>
            ))}
          </div>
        )}

        <InsightsKeyPicker options={keyOptions} value={key} onChange={setKey} />

        {/* A sort order, not a choice of which numbers arrive: every row carries
            both under either one. */}
        <div
          className="flex rounded-full bg-surface p-1"
          role="group"
          aria-label="Sort by"
        >
          <Button
            variant="ghost"
            size="sm"
            aria-pressed={sort === "count"}
            className="rounded-full aria-pressed:bg-surface-raised"
            onClick={() => setSort("count")}
          >
            Most collected
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-pressed={sort === "score"}
            className="rounded-full aria-pressed:bg-surface-raised"
            onClick={() => setSort("score")}
          >
            Best rated
          </Button>
        </div>

        {sort === "score" && (
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            Placed from
            <Input
              type="number"
              min={1}
              aria-label="Ratings needed to place in the score order"
              value={minRated}
              onChange={(event) =>
                setMinRated(Math.max(1, Number(event.target.value) || 1))
              }
              className="h-9 w-16 rounded-full text-center"
            />
            ratings up
          </label>
        )}
      </section>

      {insights.isPending && (
        <p role="status" className="mt-8 text-muted-foreground">
          Ranking…
        </p>
      )}
      {insights.isError && (
        <p role="alert" className="mt-8 text-destructive">
          Insights could not be loaded
        </p>
      )}

      {insights.data && insights.data.rows.length === 0 && (
        <p className="mt-8 text-muted-foreground">
          Nothing to rank yet for this key.
        </p>
      )}

      {nothingPlaceable && (
        <p className="mt-8 text-muted-foreground">
          Nothing is rated enough to sort by score yet — try lowering the
          threshold, or sort by how many you hold.
        </p>
      )}

      {insights.data && insights.data.rows.length > 0 && (
        <div className="mt-8">
          <InsightsRanking
            rows={ranking.placed}
            unplaced={ranking.unplaced}
            onOpen={(row) =>
              navigate(
                `/?type=${encodeURIComponent(type)}&key=${encodeURIComponent(
                  key,
                )}&value=${encodeURIComponent(row.key)}`,
              )
            }
          />
        </div>
      )}

      {insights.data && insights.data.suppressed.length > 0 && (
        <p className="mt-4 text-sm text-muted-foreground">
          {includeSuppressed ? (
            <>
              Showing{" "}
              {insights.data.suppressed.map((row) => row.label).join(", ")}.{" "}
              <button
                type="button"
                className="underline focus-ring"
                onClick={() => setIncludeSuppressed(false)}
              >
                Hide
              </button>
            </>
          ) : (
            <>
              {insights.data.suppressed.length === 1
                ? "1 value is"
                : `${insights.data.suppressed.length} values are`}{" "}
              suppressed from this ranking.{" "}
              <button
                type="button"
                className="underline focus-ring"
                onClick={() => setIncludeSuppressed(true)}
              >
                Show
              </button>
            </>
          )}
        </p>
      )}

      {insights.data &&
        (key === "year" || key === "decade") &&
        insights.data.null_count > 0 && (
          <p className="mt-2 text-sm text-muted-foreground">
            {insights.data.null_count}{" "}
            {insights.data.null_count === 1 ? "entry has" : "entries have"} no
            year and {insights.data.null_count === 1 ? "is" : "are"} not shown
            here.
          </p>
        )}
    </main>
  );
}
