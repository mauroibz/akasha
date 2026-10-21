import { createContext, useContext, useEffect, useRef } from "react";

import type { JobEvent } from "@/api/events";

export type JobListener = (event: JobEvent) => void;

export interface JobEventsValue {
  /** The latest state of every job seen on this connection, newest change first. */
  jobs: JobEvent[];
  subscribe: (listener: JobListener) => () => void;
}

export const JobEventsContext = createContext<JobEventsValue>({
  jobs: [],
  subscribe: () => () => undefined,
});

export function useJobs(): JobEvent[] {
  return useContext(JobEventsContext).jobs;
}

/** Call `listener` for every job change while the component is mounted. */
export function useJobEvent(listener: JobListener): void {
  const { subscribe } = useContext(JobEventsContext);
  const latest = useRef(listener);
  useEffect(() => {
    latest.current = listener;
  });
  useEffect(() => subscribe((event) => latest.current(event)), [subscribe]);
}

export function isActive(job: JobEvent): boolean {
  return job.state === "queued" || job.state === "running";
}
