import { useState } from "react";
import { toast } from "sonner";

import { retryJob, type JobEvent } from "@/api/events";
import { AkashaMark } from "@/components/AkashaMark";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { isActive, useJobs } from "./jobEvents";

const KIND_LABELS: Record<string, string> = {
  enrich_item: "Filling in details",
  search_import_rows: "Matching import rows",
};

function describe(job: JobEvent): string {
  const { searched, total } = job.progress;
  if (job.state === "running")
    return typeof searched === "number" && typeof total === "number"
      ? `${searched} of ${total} rows`
      : "Working";
  if (job.state === "queued")
    return job.error_code ? "Waiting to try again" : "Waiting";
  if (job.state === "failed") return job.error ?? "Failed";
  if (job.state === "cancelled") return "Cancelled";
  return "Done";
}

interface Group {
  key: string;
  label: string;
  jobs: JobEvent[];
}

/**
 * One row per batch and kind: an import of 220 books is one line saying how far it
 * has got, not 220 lines saying "Waiting". A job with no batch is its own group.
 */
function groupJobs(jobs: JobEvent[]): Group[] {
  const groups = new Map<string, Group>();
  for (const job of jobs) {
    const key = `${job.kind}:${job.batch_id ?? job.id}`;
    const group = groups.get(key) ?? {
      key,
      label: KIND_LABELS[job.kind] ?? job.kind,
      jobs: [],
    };
    group.jobs.push(job);
    groups.set(key, group);
  }
  return [...groups.values()];
}

function summarize(group: Group): string {
  if (group.jobs.length === 1)
    // A failure's reason is on its own line below, beside Retry.
    return group.jobs[0].state === "failed"
      ? "Failed"
      : describe(group.jobs[0]);
  const done = group.jobs.filter((job) => job.state === "succeeded").length;
  return `${done} of ${group.jobs.length} done`;
}

/**
 * The shell's mark, telling you background work is running (Sprint 089).
 *
 * The dot breathes while any of your jobs is queued or running; the button opens the
 * recent jobs, failures included, each failure with Retry. It replaces the decorative
 * mark in the desktop navigation, so it is a control of its own rather than a second
 * link home.
 */
export function ActivityIndicator({ className }: { className?: string }) {
  const jobs = useJobs();
  const [retrying, setRetrying] = useState<string | null>(null);
  const running = jobs.filter(isActive).length;
  const groups = groupJobs(jobs).slice(0, 8);
  const label =
    running > 0
      ? `Background work: ${running} running`
      : "Background work: nothing running";

  const retry = async (job: JobEvent) => {
    setRetrying(job.id);
    try {
      await retryJob(job.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Retry failed");
    } finally {
      setRetrying(null);
    }
  };

  return (
    <Popover>
      <PopoverTrigger
        aria-label={label}
        data-testid="activity-indicator"
        data-running={running > 0 || undefined}
        className={cn(
          "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-foreground transition-colors hover:bg-accent focus-ring",
          className,
        )}
      >
        <AkashaMark size={20} breathing={running > 0} />
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-0">
        <p className="border-b border-border px-4 py-3 text-sm font-medium">
          {running > 0
            ? `${running} job${running === 1 ? "" : "s"} running`
            : "Nothing running"}
        </p>
        {groups.length === 0 ? (
          <p className="px-4 py-3 text-sm text-muted-foreground">
            Imports and metadata look-ups show up here while they run.
          </p>
        ) : (
          <ul className="max-h-80 divide-y divide-border overflow-y-auto">
            {groups.map((group) => (
              <li key={group.key} className="px-4 py-3 text-sm">
                <span className="block font-medium">{group.label}</span>
                <span className="block text-muted-foreground">
                  {summarize(group)}
                </span>
                {group.jobs
                  .filter((job) => job.state === "failed")
                  .map((job) => (
                    <span
                      key={job.id}
                      className="mt-2 flex items-start justify-between gap-3"
                    >
                      <span className="min-w-0 truncate text-destructive">
                        {describe(job)}
                      </span>
                      <button
                        type="button"
                        onClick={() => void retry(job)}
                        disabled={retrying === job.id}
                        className="shrink-0 rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-accent focus-ring disabled:opacity-50"
                      >
                        Retry
                      </button>
                    </span>
                  ))}
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
