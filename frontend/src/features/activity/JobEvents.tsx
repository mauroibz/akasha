import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { EVENTS_URL, type JobEvent } from "@/api/events";

import { JobEventsContext, type JobListener } from "./jobEvents";

/**
 * One EventSource for the whole tab (Sprint 089), shared by the shell's activity
 * indicator and any page that wants to react to a job. The server ends each
 * connection after a few minutes and EventSource reconnects by itself, so this
 * opens once and never manages a timer.
 */
export function JobEventsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Map<string, JobEvent>>(new Map());
  const listeners = useRef(new Set<JobListener>());

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource(EVENTS_URL);
    const onJob = (message: MessageEvent<string>) => {
      let event: JobEvent;
      try {
        event = JSON.parse(message.data) as JobEvent;
      } catch {
        return;
      }
      setJobs((current) => new Map(current).set(event.id, event));
      for (const listener of listeners.current) listener(event);
    };
    source.addEventListener("job", onJob as EventListener);
    return () => {
      source.removeEventListener("job", onJob as EventListener);
      source.close();
    };
  }, []);

  const subscribe = useCallback((listener: JobListener) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const ordered = [...jobs.values()].sort((a, b) =>
    b.updated_at.localeCompare(a.updated_at),
  );
  return (
    <JobEventsContext.Provider value={{ jobs: ordered, subscribe }}>
      {children}
    </JobEventsContext.Provider>
  );
}
